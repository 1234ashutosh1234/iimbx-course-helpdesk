"""FastAPI dependency providers and lifecycle instances."""

from typing import Optional
import uuid
from fastapi import Header, HTTPException, status

from backend.database.connection import DatabaseManager, default_db_manager
from backend.services.metrics_service import MetricsService
from backend.services.cache_service import CacheService
from backend.services.idempotency import IdempotencyService
from backend.services.request_coordinator import RequestCoordinator
from backend.knowledge.retrieval import RetrievalEngine
from backend.ai.gemini_client import GeminiClient
from backend.ai.answer_generator import AnswerGenerator
from backend.services.chat_service import ChatService


# Shared singleton instances
_retrieval_engine = RetrievalEngine()
_gemini_client = GeminiClient()
_answer_generator = AnswerGenerator(
    retrieval_engine=_retrieval_engine,
    gemini_client=_gemini_client,
)
_metrics_service = MetricsService(db_manager=default_db_manager)
_cache_service = CacheService(db_manager=default_db_manager)
_idempotency_service = IdempotencyService(db_manager=default_db_manager)
_request_coordinator = RequestCoordinator(db_manager=default_db_manager)

_chat_service = ChatService(
    db_manager=default_db_manager,
    retrieval_engine=_retrieval_engine,
    gemini_client=_gemini_client,
    answer_generator=_answer_generator,
    cache_service=_cache_service,
    metrics_service=_metrics_service,
    idempotency_service=_idempotency_service,
    request_coordinator=_request_coordinator,
)


def get_db_manager() -> DatabaseManager:
    """Provide the application database manager."""
    return default_db_manager


def get_metrics_service() -> MetricsService:
    """Provide the application metrics service."""
    return _metrics_service


def get_chat_service() -> ChatService:
    """Provide the shared chat orchestration service."""
    return _chat_service


def get_gemini_client() -> GeminiClient:
    """Provide the Gemini client instance for lifecycle management."""
    return _gemini_client


def validate_idempotency_header(
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
) -> str:
    """Extract and validate the X-Idempotency-Key header.

    If missing, automatically issues a unique UUID4.
    If provided, enforces standard UUID string format.
    """
    if not x_idempotency_key or not x_idempotency_key.strip():
        return str(uuid.uuid4())

    cleaned = x_idempotency_key.strip()
    try:
        validated = str(uuid.UUID(cleaned))
        return validated
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail="Header 'X-Idempotency-Key' must be a valid UUID string.",
        )
