"""SQLite-backed response caching service with deterministic multi-factor hashing."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from backend.config import (
    CACHE_TTL_SECONDS,
    GEMINI_MODEL,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from backend.database.connection import DatabaseManager, default_db_manager
from backend.database.models import ResponseCacheRecord


class CacheService:
    """Manages persistent caching for verified, authoritative course answers."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        default_ttl_seconds: int = CACHE_TTL_SECONDS,
    ):
        """Initialize the cache service.

        Args:
            db_manager: Optional DatabaseManager instance.
            default_ttl_seconds: Cache time-to-live in seconds (default 7 days).
        """
        self.db = db_manager or default_db_manager
        self.default_ttl = default_ttl_seconds

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalize student query for deterministic comparison.

        - Converts to lowercase.
        - Strips punctuation: ? ! . , " ' ; :.
        - Collapses repeated whitespace.

        Args:
            query: Raw student question.

        Returns:
            str: Normalized query string.
        """
        cleaned = re.sub(r"[?!.,\"';:]", " ", query.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def compute_evidence_digest(evidence_text: str) -> str:
        """Compute a deterministic SHA-256 digest of the authoritative evidence text."""
        return hashlib.sha256(evidence_text.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def compute_context_fingerprint(
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """Compute a privacy-safe fingerprint of conversation context for context-sensitive questions.

        Only contextual follow-ups require this fingerprint. Context-free queries omit it.
        """
        if not conversation_context:
            return None

        # Take only the last turn role + content summary
        last_turn = conversation_context[-1]
        summary = f"{last_turn.get('role', '')}:{last_turn.get('content', '')[:100]}".strip().lower()
        return hashlib.sha256(summary.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def build_cache_key(
        intent_id: str,
        canonical_topic: str,
        corpus_version: str,
        evidence_digest: str,
        model_name: str = GEMINI_MODEL,
        prompt_version: str = PROMPT_VERSION,
        schema_version: str = SCHEMA_VERSION,
        context_fingerprint: Optional[str] = None,
    ) -> str:
        """Derive a deterministic SHA-256 cache key from multi-factor authorities.

        Args:
            intent_id: Canonical intent identifier from query classifier.
            canonical_topic: Canonical topic scope.
            corpus_version: SHA-256 hash of the 4 course documents.
            evidence_digest: SHA-256 digest of retrieved evidence.
            model_name: Configured LLM model identifier.
            prompt_version: Version of the system prompt.
            schema_version: Version of the response JSON schema.
            context_fingerprint: Optional safe hash of context if question is context-sensitive.

        Returns:
            str: 64-character hex SHA-256 cache key.
        """
        components = [
            f"intent:{intent_id.strip().lower()}",
            f"topic:{canonical_topic.strip().upper()}",
            f"corpus:{corpus_version}",
            f"evidence:{evidence_digest}",
            f"model:{model_name.strip().lower()}",
            f"prompt:{prompt_version}",
            f"schema:{schema_version}",
        ]
        if context_fingerprint:
            components.append(f"ctx:{context_fingerprint}")

        raw_key = "|".join(components)
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def get_cached_answer(self, cache_key: str) -> Optional[ResponseCacheRecord]:
        """Retrieve a valid, unexpired cached response.

        Args:
            cache_key: The SHA-256 cache key.

        Returns:
            Optional[ResponseCacheRecord]: Cached entry if found and active, else None.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        async with self.db.connection() as conn:
            async with conn.execute(
                """
                SELECT cache_key, canonical_topic, intent_id, corpus_version,
                       evidence_digest, model_name, prompt_version, response_text,
                       sources_json, is_supported, created_at, expires_at,
                       hit_count, last_accessed_at
                FROM response_cache
                WHERE cache_key = ? AND expires_at > ?;
                """,
                (cache_key, now_iso),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                return ResponseCacheRecord(
                    cache_key=row["cache_key"],
                    canonical_topic=row["canonical_topic"],
                    intent_id=row["intent_id"],
                    corpus_version=row["corpus_version"],
                    evidence_digest=row["evidence_digest"],
                    model_name=row["model_name"],
                    prompt_version=row["prompt_version"],
                    response_text=row["response_text"],
                    sources_json=row["sources_json"],
                    is_supported=bool(row["is_supported"]),
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    hit_count=row["hit_count"],
                    last_accessed_at=row["last_accessed_at"],
                )

    async def increment_cache_hit(self, cache_key: str) -> None:
        """Increment the hit count and access timestamp for a cache entry."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE response_cache
                SET hit_count = hit_count + 1,
                    last_accessed_at = ?
                WHERE cache_key = ?;
                """,
                (now_iso, cache_key),
            )

    async def save_cached_answer(
        self,
        cache_key: str,
        canonical_topic: str,
        intent_id: str,
        corpus_version: str,
        evidence_digest: str,
        response_text: str,
        sources: List[str],
        is_supported: bool = True,
        model_name: str = GEMINI_MODEL,
        prompt_version: str = PROMPT_VERSION,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Persist a validated, supported answer into response_cache.

        Safety Rules:
        - NEVER cache unsupported answers.
        - NEVER cache empty responses or missing sources.
        """
        # Strict validation: never cache unsupported or ungrounded answers
        if not is_supported:
            return False
        if not response_text or not response_text.strip():
            return False
        if not sources:
            return False

        now = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = (now + timedelta(seconds=ttl)).isoformat()
        now_iso = now.isoformat()
        sources_json = json.dumps(sources)

        async with self.db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO response_cache (
                    cache_key, canonical_topic, intent_id, corpus_version,
                    evidence_digest, model_name, prompt_version, response_text,
                    sources_json, is_supported, created_at, expires_at,
                    hit_count, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_text = excluded.response_text,
                    sources_json = excluded.sources_json,
                    expires_at = excluded.expires_at,
                    last_accessed_at = excluded.last_accessed_at;
                """,
                (
                    cache_key,
                    canonical_topic,
                    intent_id,
                    corpus_version,
                    evidence_digest,
                    model_name,
                    prompt_version,
                    response_text.strip(),
                    sources_json,
                    1,
                    now_iso,
                    expires_at,
                    now_iso,
                ),
            )
        return True

    async def cleanup_expired_cache(self) -> int:
        """Purge all expired entries from response_cache.

        Returns:
            int: Number of purged cache rows.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM response_cache WHERE expires_at <= ?;",
                (now_iso,),
            )
            return cursor.rowcount
