"""SQLite schema definitions and DDL scripts for IIMBx Helpdesk."""

# Migration 1: Baseline production schema
SCHEMA_V1 = """
-- Schema Migrations Tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT NOT NULL
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES conversations(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, created_at);

-- Response Cache (Ground truth validated answers only)
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    canonical_topic TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    response_text TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    is_supported INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache (expires_at);
CREATE INDEX IF NOT EXISTS idx_cache_intent ON response_cache (intent_id);

-- System Metrics (Atomic counters)
CREATE TABLE IF NOT EXISTS system_metrics (
    metric_key TEXT PRIMARY KEY,
    metric_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Pre-populate default metrics
INSERT OR IGNORE INTO system_metrics (metric_key, metric_value, updated_at)
VALUES ('total_questions', 0, datetime('now'));

INSERT OR IGNORE INTO system_metrics (metric_key, metric_value, updated_at)
VALUES ('gemini_calls', 0, datetime('now'));

INSERT OR IGNORE INTO system_metrics (metric_key, metric_value, updated_at)
VALUES ('cache_hits', 0, datetime('now'));

-- Idempotency Keys (Per-request double-click protection)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed')),
    response_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys (expires_at);
CREATE INDEX IF NOT EXISTS idx_idempotency_session ON idempotency_keys (session_id);

-- In-flight Requests (Inter-request / inter-process coalescing & leader lease)
CREATE TABLE IF NOT EXISTS inflight_requests (
    request_fingerprint TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed')),
    response_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflight_lease ON inflight_requests (lease_expires_at);
"""
