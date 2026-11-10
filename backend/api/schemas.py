"""Pydantic request and response schemas for FastAPI endpoints."""

from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Payload for student chat inquiry."""
    session_id: str = Field(..., description="Unique student session UUID")
    message: str = Field(..., min_length=1, max_length=1000, description="Student question")

    @field_validator("session_id")
    @classmethod
    def validate_session_uuid(cls, v: str) -> str:
        try:
            val = str(uuid.UUID(str(v).strip()))
            return val
        except (ValueError, AttributeError):
            raise ValueError("session_id must be a valid UUID string.")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank or whitespace-only.")
        return cleaned


class ChatMetrics(BaseModel):
    """Live telemetry counters snapshot."""
    total_questions: int = Field(0, description="Total unique logical student questions accepted")
    gemini_calls: int = Field(0, description="Actual outbound Gemini API generation attempts")
    cache_hits: int = Field(0, description="Answers served directly from persistent cache")


class ChatResponseSchema(BaseModel):
    """Authoritative API response schema for student inquiry."""
    answer: str
    sources: List[str]
    is_supported: bool
    served_from_cache: bool
    session_id: str
    metrics: ChatMetrics


class MetricsResponseSchema(BaseModel):
    """Payload returned by GET /api/metrics."""
    total_questions: int
    gemini_calls: int
    cache_hits: int


class HealthResponseSchema(BaseModel):
    """Payload returned by GET /api/health."""
    status: str
    database: str
    version: str = "1.0.0"


class ConversationResetRequest(BaseModel):
    """Payload for resetting student conversation session."""
    session_id: str = Field(..., description="Session UUID to reset")

    @field_validator("session_id")
    @classmethod
    def validate_session_uuid(cls, v: str) -> str:
        try:
            return str(uuid.UUID(str(v).strip()))
        except (ValueError, AttributeError):
            raise ValueError("session_id must be a valid UUID string.")


class ConversationResetResponse(BaseModel):
    """Confirmation payload for session reset."""
    session_id: str
    cleared_messages_count: int
    message: str


class ErrorDetail(BaseModel):
    """Standardized error response without secret or stack trace leakage."""
    error: str
    detail: Optional[str] = None
