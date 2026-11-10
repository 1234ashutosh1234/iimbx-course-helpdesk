"""Chat orchestration service coordinating retrieval, caching, idempotency, and AI generation."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from backend.config import (
    GEMINI_MODEL,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from backend.database.connection import DatabaseManager, default_db_manager
from backend.knowledge.schemas import CanonicalTopic, EvidenceObject
from backend.knowledge.retrieval import RetrievalEngine
from backend.ai.answer_generator import AnswerGenerator, AnswerResult
from backend.ai.gemini_client import GeminiClient
from backend.services.cache_service import CacheService
from backend.services.metrics_service import MetricsService
from backend.services.idempotency import (
    IdempotencyService,
    IdempotencyConflictError,
)
from backend.services.request_coordinator import RequestCoordinator


class ChatResponse(BaseModel):
    """Structured response payload returned by ChatService."""
    answer: str
    sources: List[str]
    canonical_topic: str
    is_supported: bool
    cache_hit: bool = False
    is_fallback: bool = False
    is_idempotent_replay: bool = False
    metrics: Optional[Dict[str, int]] = None


class ChatService:
    """End-to-end orchestrator for student queries with caching, idempotency, and live telemetry."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        retrieval_engine: Optional[RetrievalEngine] = None,
        gemini_client: Optional[GeminiClient] = None,
        answer_generator: Optional[AnswerGenerator] = None,
        cache_service: Optional[CacheService] = None,
        metrics_service: Optional[MetricsService] = None,
        idempotency_service: Optional[IdempotencyService] = None,
        request_coordinator: Optional[RequestCoordinator] = None,
    ):
        """Initialize all dependent sub-services."""
        self.db = db_manager or default_db_manager
        self.retrieval_engine = retrieval_engine or RetrievalEngine()
        self.gemini_client = gemini_client or GeminiClient()
        self.answer_generator = answer_generator or AnswerGenerator(
            retrieval_engine=self.retrieval_engine,
            gemini_client=self.gemini_client,
        )
        self.cache_service = cache_service or CacheService(db_manager=self.db)
        self.metrics_service = metrics_service or MetricsService(db_manager=self.db)
        self.idempotency_service = idempotency_service or IdempotencyService(db_manager=self.db)
        self.request_coordinator = request_coordinator or RequestCoordinator(db_manager=self.db)

        # Instrument Gemini client outbound attempts directly into metrics_service
        self.gemini_client.set_call_hook(self.metrics_service.increment_gemini_calls)

    async def _ensure_conversation(self, session_id: str) -> None:
        """Upsert conversation session record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (session_id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at;
                """,
                (session_id, now_iso, now_iso),
            )

    async def _persist_messages(
        self,
        session_id: str,
        user_query: str,
        assistant_answer: str,
        sources: List[str],
    ) -> None:
        """Persist user inquiry and assistant response turn into messages table."""
        now_iso = datetime.now(timezone.utc).isoformat()
        sources_json = json.dumps(sources)
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources_json, created_at)
                VALUES (?, 'user', ?, '[]', ?);
                """,
                (session_id, user_query, now_iso),
            )
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources_json, created_at)
                VALUES (?, 'assistant', ?, ?, ?);
                """,
                (session_id, assistant_answer, sources_json, now_iso),
            )

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns for context-sensitive inquiries."""
        async with self.db.connection() as conn:
            async with conn.execute(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?;
                """,
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def process_question(
        self,
        question: str,
        session_id: str,
        idempotency_key: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> ChatResponse:
        """Process a student inquiry through the complete verified lifecycle."""
        # Step 1: Input Validation
        if not question or not question.strip():
            raise ValueError("Student question cannot be empty.")
        if not session_id or not session_id.strip():
            raise ValueError("Session ID cannot be empty.")
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key cannot be empty.")

        clean_question = question.strip()
        clean_session = session_id.strip()
        clean_idempotency_key = idempotency_key.strip()

        # Step 2 & 3: Idempotency Check & Registration
        request_hash = IdempotencyService.compute_request_hash(clean_session, clean_question)
        status, existing_data = await self.idempotency_service.check_or_register_key(
            idempotency_key=clean_idempotency_key,
            session_id=clean_session,
            request_hash=request_hash,
        )

        # CASE A: Previously completed request replay
        if status == "completed" and existing_data is not None:
            metrics = await self.metrics_service.get_metrics()
            return ChatResponse(
                answer=existing_data["answer"],
                sources=existing_data["sources"],
                canonical_topic=existing_data["canonical_topic"],
                is_supported=existing_data["is_supported"],
                cache_hit=existing_data.get("cache_hit", False),
                is_fallback=existing_data.get("is_fallback", False),
                is_idempotent_replay=True,
                metrics=metrics,
            )

        # CASE B: Request currently in progress
        if status == "processing":
            awaited = await self.idempotency_service.wait_for_in_progress(
                clean_idempotency_key, timeout_seconds=5.0
            )
            if awaited is not None:
                metrics = await self.metrics_service.get_metrics()
                return ChatResponse(
                    answer=awaited["answer"],
                    sources=awaited["sources"],
                    canonical_topic=awaited["canonical_topic"],
                    is_supported=awaited["is_supported"],
                    cache_hit=awaited.get("cache_hit", False),
                    is_fallback=awaited.get("is_fallback", False),
                    is_idempotent_replay=True,
                    metrics=metrics,
                )
            metrics = await self.metrics_service.get_metrics()
            return ChatResponse(
                answer="Request currently being processed. Please refresh in a moment.",
                sources=[],
                canonical_topic="IN_PROGRESS",
                is_supported=False,
                cache_hit=False,
                is_idempotent_replay=True,
                metrics=metrics,
            )

        # New accepted request: Increment total_questions exactly once
        await self.metrics_service.increment_total_questions()
        await self._ensure_conversation(clean_session)

        # Step 4 & 5: Query Classification and Authoritative Evidence Retrieval
        evidence: EvidenceObject = self.retrieval_engine.retrieve(
            question=clean_question,
            conversation_context=conversation_context,
        )

        topic = evidence.canonical_topic
        topics = getattr(evidence, "canonical_topics", None) or [topic]
        topic_str = "+".join(sorted(t.value for t in topics))

        # Step 6: Handle Unsupported Questions (Zero Gemini Calls, No Cache Entry)
        if not evidence.is_supported or any(
            t in {
                CanonicalTopic.REFUND_POLICY,
                CanonicalTopic.SQL_INDEXING_AND_KUBERNETES,
                CanonicalTopic.OFF_TOPIC,
                CanonicalTopic.UNKNOWN,
            }
            for t in topics
        ):
            unsupported_dict = {
                "answer": evidence.evidence,
                "sources": evidence.source_files,
                "canonical_topic": topic_str,
                "is_supported": False,
                "cache_hit": False,
                "is_fallback": False,
            }
            await self._persist_messages(
                clean_session, clean_question, evidence.evidence, evidence.source_files
            )
            await self.idempotency_service.complete_key(clean_idempotency_key, unsupported_dict)
            metrics = await self.metrics_service.get_metrics()
            return ChatResponse(**unsupported_dict, metrics=metrics)

        # Step 7: Build Multi-Factor Deterministic Cache Key
        evidence_digest = CacheService.compute_evidence_digest(evidence.evidence)
        is_context_dependent = bool(
            conversation_context and evidence.metadata.get("requires_context", False)
        )
        context_fingerprint = (
            CacheService.compute_context_fingerprint(conversation_context)
            if is_context_dependent
            else None
        )
        cache_key = CacheService.build_cache_key(
            intent_id=evidence.intent_id,
            canonical_topic=topic_str,
            corpus_version=evidence.corpus_version,
            evidence_digest=evidence_digest,
            model_name=self.gemini_client.model,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            context_fingerprint=context_fingerprint,
        )

        # Step 8: Persistent Cache Lookup
        cached_entry = await self.cache_service.get_cached_answer(cache_key)
        if cached_entry is not None:
            # Cache hit: Increment cache_hits counter exactly once
            await self.metrics_service.increment_cache_hits()
            await self.cache_service.increment_cache_hit(cache_key)

            sources = json.loads(cached_entry.sources_json)
            cached_dict = {
                "answer": cached_entry.response_text,
                "sources": sources,
                "canonical_topic": cached_entry.canonical_topic,
                "is_supported": True,
                "cache_hit": True,
                "is_fallback": False,
            }
            await self._persist_messages(
                clean_session, clean_question, cached_entry.response_text, sources
            )
            await self.idempotency_service.complete_key(clean_idempotency_key, cached_dict)
            metrics = await self.metrics_service.get_metrics()
            return ChatResponse(**cached_dict, metrics=metrics)

        # Step 9: In-Flight Generation Coordination
        # The cache_key uniquely identifies this exact generation requirement
        request_fingerprint = cache_key
        owner_id = str(uuid.uuid4())
        is_leader = await self.request_coordinator.try_acquire_leader(
            fingerprint=request_fingerprint,
            owner_id=owner_id,
        )

        if not is_leader:
            # Follower: Await leader's completion
            coalesced_result = await self.request_coordinator.await_result(
                fingerprint=request_fingerprint,
                timeout_seconds=30.0,
            )
            if coalesced_result is not None:
                # IMPORTANT: Coalesced in-flight results are NOT counted as persistent cache hits
                coalesced_dict = dict(coalesced_result)
                coalesced_dict["cache_hit"] = False
                await self._persist_messages(
                    clean_session,
                    clean_question,
                    coalesced_dict["answer"],
                    coalesced_dict["sources"],
                )
                await self.idempotency_service.complete_key(
                    clean_idempotency_key, coalesced_dict
                )
                metrics = await self.metrics_service.get_metrics()
                return ChatResponse(**coalesced_dict, metrics=metrics)

            # If leader timed out or failed, become generation leader
            is_leader = True

        # Step 10: Generation Leader Execution
        try:
            answer_result: AnswerResult = await self.answer_generator.generate_answer(
                question=clean_question,
                conversation_context=conversation_context,
            )

            # Step 11: Persist Only Validated Supported Answers to Cache
            if answer_result.is_supported:
                await self.cache_service.save_cached_answer(
                    cache_key=cache_key,
                    canonical_topic=answer_result.canonical_topic,
                    intent_id=answer_result.intent_id,
                    corpus_version=answer_result.corpus_version,
                    evidence_digest=evidence_digest,
                    response_text=answer_result.answer,
                    sources=answer_result.sources,
                    is_supported=answer_result.is_supported,
                    model_name=self.gemini_client.model,
                    prompt_version=PROMPT_VERSION,
                )

            result_dict = {
                "answer": answer_result.answer,
                "sources": answer_result.sources,
                "canonical_topic": answer_result.canonical_topic,
                "is_supported": answer_result.is_supported,
                "cache_hit": False,
                "is_fallback": answer_result.is_fallback,
            }

            # Complete in-flight record for waiting followers
            await self.request_coordinator.complete_leader(
                fingerprint=request_fingerprint,
                owner_id=owner_id,
                response_data=result_dict,
            )

            # Persist turn and complete idempotency key
            await self._persist_messages(
                clean_session, clean_question, answer_result.answer, answer_result.sources
            )
            await self.idempotency_service.complete_key(clean_idempotency_key, result_dict)

            metrics = await self.metrics_service.get_metrics()
            return ChatResponse(**result_dict, metrics=metrics)

        except Exception as e:
            # Release leader lease on exception
            await self.request_coordinator.fail_leader(request_fingerprint, owner_id)
            await self.idempotency_service.fail_key(clean_idempotency_key)
            raise e
