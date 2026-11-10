"""Structured answer generator coordinating retrieval, generation, and validation."""

import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from backend.knowledge.schemas import CanonicalTopic, EvidenceObject
from backend.knowledge.retrieval import RetrievalEngine
from backend.knowledge.policy_resolver import PolicyResolver
from backend.ai.gemini_client import GeminiClient
from backend.ai.prompts import SYSTEM_INSTRUCTION, build_generation_prompt
from backend.ai.response_validator import ResponseValidator
from backend.ai.exceptions import GeminiError


class GeneratedAnswer(BaseModel):
    """Pydantic schema enforcing structured JSON response generation from Gemini."""
    answer: str = Field(description="The conversational answer grounded strictly in the official evidence.")


class AnswerResult(BaseModel):
    """Authoritative answer package returned by the AI AnswerGenerator to the application layer."""
    answer: str
    sources: List[str]
    canonical_topic: str
    is_supported: bool
    corpus_version: str
    intent_id: str
    confidence: float
    is_fallback: bool = False
    validation_note: Optional[str] = None


class AnswerGenerator:
    """Coordinates deterministic retrieval, Gemini AI generation, and factual validation."""

    def __init__(
        self,
        retrieval_engine: Optional[RetrievalEngine] = None,
        gemini_client: Optional[GeminiClient] = None,
    ):
        """Initialize generator with retrieval engine and Gemini client.
        
        Args:
            retrieval_engine: Optional RetrievalEngine instance.
            gemini_client: Optional GeminiClient instance.
        """
        self.retrieval_engine = retrieval_engine or RetrievalEngine()
        self.gemini_client = gemini_client or GeminiClient()

    async def generate_answer(
        self,
        question: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> AnswerResult:
        """Process a student inquiry through deterministic retrieval, AI generation, and validation.

        Lifecycle:
        1. Query classification and deterministic retrieval.
        2. If unsupported topic: return deterministic response without invoking Gemini.
        3. If supported: generate answer with Gemini using structured output schema.
        4. Validate generated answer against mandatory factual anchors.
        5. If validation fails or Gemini encounters transient error: fall back to trusted PolicyFact.
        6. Return AnswerResult with sources derived strictly from Python evidence.
        """
        # Step 1: Deterministic Retrieval
        evidence: EvidenceObject = self.retrieval_engine.retrieve(
            question=question,
            conversation_context=conversation_context
        )

        topic = evidence.canonical_topic

        # Step 2: Handle Unsupported Inquiries (Zero Gemini API Calls)
        if not evidence.is_supported or topic in {
            CanonicalTopic.REFUND_POLICY,
            CanonicalTopic.SQL_INDEXING_AND_KUBERNETES,
            CanonicalTopic.OFF_TOPIC,
            CanonicalTopic.UNKNOWN,
        }:
            return AnswerResult(
                answer=evidence.evidence,
                sources=evidence.source_files,
                canonical_topic=topic.value,
                is_supported=False,
                corpus_version=evidence.corpus_version,
                intent_id=evidence.intent_id,
                confidence=evidence.confidence,
                is_fallback=False,
            )

        # Step 3: Format Prompt for Supported Inquiries
        prompt = build_generation_prompt(evidence, conversation_context)

        # Step 4: Invoke Gemini AI with Structured Output
        raw_response: Optional[str] = None
        generation_error: Optional[str] = None

        try:
            raw_response = await self.gemini_client.generate_content_async(
                prompt=prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                response_schema=GeneratedAnswer,
            )
        except GeminiError as ge:
            generation_error = str(ge)
        except Exception as e:
            generation_error = f"Unexpected generation failure: {e}"

        # If Gemini failed or returned non-string, use deterministic fallback directly
        if raw_response is None or not isinstance(raw_response, str):
            fallback_text = ResponseValidator.get_fallback_answer(topic)
            return AnswerResult(
                answer=fallback_text,
                sources=evidence.source_files,
                canonical_topic=topic.value,
                is_supported=True,
                corpus_version=evidence.corpus_version,
                intent_id=evidence.intent_id,
                confidence=evidence.confidence,
                is_fallback=True,
                validation_note=f"Gemini call failed ({generation_error}); used authoritative fallback.",
            )

        # Step 5: Parse Structured JSON
        parsed_answer_text: str = ""
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict) and "answer" in parsed:
                parsed_answer_text = str(parsed["answer"]).strip()
            else:
                # Fallback to raw text if not dict
                parsed_answer_text = raw_response.strip()
        except json.JSONDecodeError:
            parsed_answer_text = raw_response.strip()

        # Step 6: Validate Mandatory Factual Anchors
        is_valid, failure_reason = ResponseValidator.validate(topic, parsed_answer_text)

        if not is_valid:
            # AI omitted essential fact or contradicted policy -> fallback to trusted PolicyFact
            fallback_text = ResponseValidator.get_fallback_answer(topic)
            return AnswerResult(
                answer=fallback_text,
                sources=evidence.source_files,
                canonical_topic=topic.value,
                is_supported=True,
                corpus_version=evidence.corpus_version,
                intent_id=evidence.intent_id,
                confidence=evidence.confidence,
                is_fallback=True,
                validation_note=f"Validation failed: {failure_reason}. Used authoritative fallback.",
            )

        # Validated AI generation succeeded!
        return AnswerResult(
            answer=parsed_answer_text,
            sources=evidence.source_files,  # Strictly from Python evidence!
            canonical_topic=topic.value,    # Strictly from Python classifier!
            is_supported=True,              # Strictly from Python retrieval!
            corpus_version=evidence.corpus_version,
            intent_id=evidence.intent_id,
            confidence=evidence.confidence,
            is_fallback=False,
        )
