"""Data transfer and record models for SQLite storage."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


def current_utc_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class ConversationRecord(BaseModel):
    """Represents a student conversation session."""
    session_id: str
    created_at: str = Field(default_factory=current_utc_iso)
    updated_at: str = Field(default_factory=current_utc_iso)


class MessageRecord(BaseModel):
    """Represents a single turn in a conversation."""
    id: Optional[int] = None
    session_id: str
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    sources_json: str = "[]"
    created_at: str = Field(default_factory=current_utc_iso)


class ResponseCacheRecord(BaseModel):
    """Represents a cached authoritative response."""
    cache_key: str
    canonical_topic: str
    intent_id: str
    corpus_version: str
    evidence_digest: str
    model_name: str
    prompt_version: str
    response_text: str
    sources_json: str
    is_supported: bool = True
    created_at: str = Field(default_factory=current_utc_iso)
    expires_at: str
    hit_count: int = 0
    last_accessed_at: str = Field(default_factory=current_utc_iso)


class SystemMetricRecord(BaseModel):
    """Represents an atomic telemetry metric."""
    metric_key: str
    metric_value: int = 0
    updated_at: str = Field(default_factory=current_utc_iso)


class IdempotencyRecord(BaseModel):
    """Represents an in-flight or completed idempotent request."""
    idempotency_key: str
    session_id: str
    request_hash: str
    status: str  # 'processing' | 'completed' | 'failed'
    response_json: Optional[str] = None
    created_at: str = Field(default_factory=current_utc_iso)
    updated_at: str = Field(default_factory=current_utc_iso)
    expires_at: str


class InflightRequestRecord(BaseModel):
    """Represents a request coordination lease for in-flight generation."""
    request_fingerprint: str
    owner_id: str
    status: str  # 'processing' | 'completed' | 'failed'
    response_json: Optional[str] = None
    created_at: str = Field(default_factory=current_utc_iso)
    updated_at: str = Field(default_factory=current_utc_iso)
    lease_expires_at: str
