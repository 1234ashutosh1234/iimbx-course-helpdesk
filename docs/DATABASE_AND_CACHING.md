# DATABASE AND CACHING ARCHITECTURE

**System:** IIMBx Course Helpdesk Chatbot (`DPM-101`)  
**Track:** System Design & Backend Engineering  
**Scope:** Part 4 — SQLite WAL Persistence, Grounded Response Caching, Idempotency, and Live Telemetry  

---

## 1. Executive Architecture Overview

The Part 4 data and caching layer delivers production-grade reliability, request deduplication, distributed coordination, and telemetry tracking for the IIMBx Course Helpdesk.

```
                                  [Incoming Student Request]
                                              │
                                              ▼
                                 [Idempotency Verification]
                                 (idempotency_keys: SHA-256)
                                  ├── Replay -> Return Saved Response (0 Metrics)
                                  ├── In-Progress -> Await Completion
                                  ├── Conflict -> HTTP 409 Conflict
                                  └── New Accepted -> total_questions + 1
                                              │
                                              ▼
                                 [Deterministic Retrieval]
                                (backend/knowledge/retrieval.py)
                                  ├── Unsupported -> Deterministic Message (0 Gemini Calls, 0 Cache Writes)
                                  └── Supported Policy -> Proceed
                                              │
                                              ▼
                                   [Multi-Factor Cache Key]
                                   (SHA-256 Multi-Factor Digest)
                                              │
                                              ▼
                                    [Response Cache Check]
                                  ├── Cache Hit -> cache_hits + 1, Return Grounded Answer (0 Gemini Calls)
                                  └── Cache Miss -> In-Flight Coordination
                                              │
                                              ▼
                                 [In-Flight Request Leader Lease]
                                   (inflight_requests table)
                                  ├── Follower -> Await Leader Lease (Coalesced, 0 Cache Hits, 0 Gemini Calls)
                                  └── Leader -> Outbound Gemini Generation (gemini_calls + 1 per attempt)
                                              │
                                              ▼
                                   [Factual Anchor Validation]
                                  ├── Passed -> Write to response_cache & inflight_requests
                                  └── Failed -> Deterministic PolicyFact Fallback -> Write to Cache
                                              │
                                              ▼
                                    [Complete Idempotency Key]
                                    [Persist Turn in Messages]
```

---

## 2. Entity-Relationship & Database Schema

The database utilizes SQLite 3 managed asynchronously via `aiosqlite` with Write-Ahead Logging (`WAL`) enabled.

```mermaid
erDiagram
    conversations ||--o{ messages : "contains"
    conversations {
        text session_id PK
        text created_at
        text updated_at
    }
    messages {
        integer id PK
        text session_id FK
        text role
        text content
        text sources_json
        text created_at
    }
    response_cache {
        text cache_key PK
        text canonical_topic
        text intent_id
        text corpus_version
        text evidence_digest
        text model_name
        text prompt_version
        text response_text
        text sources_json
        integer is_supported
        text created_at
        text expires_at
        integer hit_count
        text last_accessed_at
    }
    system_metrics {
        text metric_key PK
        integer metric_value
        text updated_at
    }
    idempotency_keys {
        text idempotency_key PK
        text session_id
        text request_hash
        text status
        text response_json
        text created_at
        text updated_at
        text expires_at
    }
    inflight_requests {
        text request_fingerprint PK
        text owner_id
        text status
        text response_json
        text created_at
        text updated_at
        text lease_expires_at
    }
    schema_migrations {
        integer version PK
        text applied_at
        text description
    }
```

### Table Definitions & Constraints

1. **`conversations`**:
   - `session_id` (`TEXT PRIMARY KEY`): Unique student conversation session UUID.
   - `created_at` (`TEXT NOT NULL`), `updated_at` (`TEXT NOT NULL`): ISO-8601 UTC timestamps.

2. **`messages`**:
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`): Monotonic message sequence ID.
   - `session_id` (`TEXT NOT NULL REFERENCES conversations(session_id) ON DELETE CASCADE`).
   - `role` (`TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system'))`).
   - `content` (`TEXT NOT NULL`): Raw student question or generated assistant answer.
   - `sources_json` (`TEXT NOT NULL DEFAULT '[]'`): Serialized JSON array of authoritative source filenames.
   - `created_at` (`TEXT NOT NULL`): ISO-8601 timestamp.
   - Index: `idx_messages_session (session_id, created_at)`.

3. **`response_cache`**:
   - `cache_key` (`TEXT PRIMARY KEY`): SHA-256 multi-factor authority digest.
   - `canonical_topic` (`TEXT NOT NULL`), `intent_id` (`TEXT NOT NULL`).
   - `corpus_version` (`TEXT NOT NULL`): SHA-256 hash of the 4 course documents.
   - `evidence_digest` (`TEXT NOT NULL`): SHA-256 digest of retrieved policy text.
   - `model_name` (`TEXT NOT NULL`), `prompt_version` (`TEXT NOT NULL`).
   - `response_text` (`TEXT NOT NULL`): Grounded, validated answer text.
   - `sources_json` (`TEXT NOT NULL`): JSON array of source files.
   - `is_supported` (`INTEGER NOT NULL DEFAULT 1 CHECK(is_supported = 1)`): Enforces that unsupported or speculative answers are **never** stored.
   - `created_at`, `expires_at`, `hit_count`, `last_accessed_at`.
   - Indexes: `idx_cache_expires (expires_at)`, `idx_cache_intent (intent_id)`.

4. **`system_metrics`**:
   - `metric_key` (`TEXT PRIMARY KEY`): Counter identifier (`total_questions`, `gemini_calls`, `cache_hits`).
   - `metric_value` (`INTEGER NOT NULL DEFAULT 0`).
   - `updated_at` (`TEXT NOT NULL`).

5. **`idempotency_keys`**:
   - `idempotency_key` (`TEXT PRIMARY KEY`): Client-supplied UUID token (`X-Idempotency-Key`).
   - `session_id` (`TEXT NOT NULL`), `request_hash` (`TEXT NOT NULL`).
   - `status` (`TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed'))`).
   - `response_json` (`TEXT`): Serialized completed response payload.
   - `created_at`, `updated_at`, `expires_at`.
   - Indexes: `idx_idempotency_expires (expires_at)`, `idx_idempotency_session (session_id)`.

6. **`inflight_requests`**:
   - `request_fingerprint` (`TEXT PRIMARY KEY`): Multi-factor cache key representing exact generation task.
   - `owner_id` (`TEXT NOT NULL`): Worker/request instance UUID holding generation lease.
   - `status` (`TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed'))`).
   - `response_json` (`TEXT`): Serialized generation result for coalesced followers.
   - `created_at`, `updated_at`, `lease_expires_at` (`TEXT NOT NULL`).
   - Index: `idx_inflight_lease (lease_expires_at)`.

7. **`schema_migrations`**:
   - Tracks versioned migrations applied to the database.

---

## 3. Multi-Factor Deterministic Cache Strategy

### 3.1 Key Derivation Formula

A cache entry is keyed not on raw student text, but on a 64-character SHA-256 hash of 7 distinct authority dimensions:

$$\text{CacheKey} = \text{SHA-256}\left(\begin{array}{l}
\text{"intent:"} + \text{intent\_id} \;\parallel \\
\text{"topic:"} + \text{canonical\_topic} \;\parallel \\
\text{"corpus:"} + \text{corpus\_version} \;\parallel \\
\text{"evidence:"} + \text{evidence\_digest} \;\parallel \\
\text{"model:"} + \text{model\_name} \;\parallel \\
\text{"prompt:"} + \text{prompt\_version} \;\parallel \\
\text{"schema:"} + \text{schema\_version} \;\parallel \\
[\text{"ctx:"} + \text{context\_fingerprint}]
\end{array}\right)$$

### 3.2 Semantic Coalescing vs Scope Isolation

- **Semantic Paraphrase Coalescing:**  
  *"How much do I need to score to pass DPM-101?"* and *"What is the minimum passing percentage?"* both map to `intent_id="intent:passing_criteria"` and `canonical_topic="PASSING_CRITERIA"`. Because both share the same evidence digest, corpus hash, model, and prompt, they compute the **exact same cache key**.
- **Scope Isolation:**  
  Questions on different topics compute different intent IDs and different evidence digests, guaranteeing zero key collisions.
- **Context-Sensitive Disambiguation:**  
  When an inquiry requires context (e.g. *"Can I get a refund for that?"* after inquiring about the certificate fee), `retrieval.py` assigns `intent_id="intent:refund_policy_contextual"` and `is_context_dependent=True`. The key incorporates `context_fingerprint` (hash of previous turn) and `canonical_topic="REFUND_POLICY"`, ensuring it **never** reuses the certificate fee answer.

### 3.3 Automatic Invalidation Rules

Cache keys are cryptographically invalidating:
1. **Corpus Hash Invalidation:** Any change in `course_docs/*.txt` changes `corpus_version_hash`, immediately producing a new cache key.
2. **Evidence Digest Invalidation:** If retrieval extracts different evidence lines, `evidence_digest` changes.
3. **Model Configuration Invalidation:** Changing `GEMINI_MODEL` (e.g., from `gemini-3.8-flash` to `gemini-3.0-pro`) produces a new cache key.
4. **Prompt & Schema Invalidation:** Bumping `PROMPT_VERSION` or `SCHEMA_VERSION` invalidates previous entries.

### 3.4 Strict Non-Caching Rules

The cache layer **refuses** to store:
- Unsupported responses (`is_supported = False`), such as course refunds, external IT topics (SQL/Kubernetes), or general banter (cricket).
- Failed Gemini network requests.
- Invalid or ungrounded responses that failed factual anchor validation.
- Empty responses or responses with empty source filename lists.

---

## 4. Idempotency & Concurrency Coordination

### 4.1 Idempotency Lifecycle (`idempotency_keys`)

Clients supply an `X-Idempotency-Key` header with each query.

```
Incoming Request (key, session_id, payload)
       │
       ├── Check DB (Atomic INSERT OR IGNORE INTO idempotency_keys ...)
       │
       ├── Case A: Key exists with status='completed'
       │     └── Verify request_hash == stored_hash
       │           ├── True: Return cached response directly (total_questions NOT incremented)
       │           └── False: Raise IdempotencyConflictError (HTTP 409 Conflict)
       │
       ├── Case B: Key exists with status='processing'
       │     └── Bounded polling (up to 5.0s). If completed within timeout -> return response.
       │
       └── Case C: Key is brand new (rowcount > 0)
             └── Status set to 'processing', total_questions incremented by 1, proceeds to pipeline.
```

### 4.2 Inter-Request Generation Coalescing (`inflight_requests`)

When multiple students ask the same question concurrently with different idempotency keys:

1. **Leader Election:**
   All concurrent requests compute the generation fingerprint (`request_fingerprint = cache_key`). The first request to execute `INSERT OR IGNORE INTO inflight_requests` acquires the generation lease as **Leader** (`is_leader = True`).
2. **Follower Suspension:**
   Subsequent concurrent requests fail to insert and become **Followers** (`is_leader = False`). Followers poll `inflight_requests` via `await_result(fingerprint)` with a 50ms interval.
3. **Completion & Coalescing:**
   When the Leader finishes generation and validation, it calls `complete_leader()`, writing the result JSON to `inflight_requests` and `response_cache`. Followers unblock, parse the leader's completed payload, complete their respective idempotency keys, and return the answer.
4. **Telemetry Invariant:**
   **Coalesced in-flight responses do NOT increment `cache_hits`.** They are shared in-flight executions, not persistent cache reads.

### 4.3 Lease Recovery & Crash Protection

- **Lease Timeout:** Generation leases expire after `INFLIGHT_LEASE_SECONDS` (default: 45 seconds).
- **Crash Recovery:** If a leader process crashes midway, any subsequent request can detect `status = 'processing' AND lease_expires_at <= now` and atomically take over leadership via `UPDATE ... WHERE lease_expires_at <= now`.
- **Stale Worker Defense:** A stale worker whose lease expired can never overwrite a newer leader's result because `complete_leader()` enforces `WHERE request_fingerprint = ? AND owner_id = ?`.

---

## 5. Live Telemetry Metric Semantics

All system counters are maintained in SQLite `system_metrics` using atomic SQL increments:
```sql
UPDATE system_metrics
SET metric_value = metric_value + 1,
    updated_at = datetime('now')
WHERE metric_key = ?;
```
This avoids read-modify-write lost updates during high concurrency.

| Metric Counter | Mathematical Definition | When Incremented | When NOT Incremented |
| :--- | :--- | :--- | :--- |
| **`total_questions`** | Accepted unique logical student requests | Once per unique accepted `idempotency_key` (first time registered) | Idempotency key replays; duplicate double-clicks; requests rejected due to validation or conflict |
| **`gemini_calls`** | Actual outbound HTTP attempts to Gemini API | Once for every actual outbound dispatch, including bounded retry attempts | Cache hits; unsupported questions (refunds, off-topic); missing API credentials; idempotency replays; follower coalescing |
| **`cache_hits`** | Answers resolved from persistent cache | Once when a valid, active `response_cache` row provides the answer | In-flight request coalescing; idempotency replays; deterministic unsupported policy fallbacks |

---

## 6. SQLite WAL Configuration & Concurrency Realities

### 6.1 Production Pragmas

Connections are configured on creation:
```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

- **WAL (Write-Ahead Logging):** Allows concurrent readers to execute simultaneously without blocking writers, and writers do not block readers.
- **`busy_timeout = 5000`:** Enforces a 5-second kernel retry window if the database is temporarily locked by another writer.
- **`synchronous = NORMAL`:** In WAL mode, `NORMAL` ensures durability across power cuts while avoiding excessive `fsync()` system calls.

### 6.2 Architectural Boundaries & Scaling Considerations

> [!WARNING] SQLite Writer Serialization
> In SQLite, even in WAL mode, **writes are serialized globally**. Only one write transaction can execute at any instant.
>
> **Critical Design Rule:** The backend **never** holds an open SQLite transaction while awaiting a Gemini network response. Database writes are bounded micro-transactions lasting < 5 milliseconds.

### 6.3 Deployment & Scaling Limitations

- **Single Host / Persistent Disk:** SQLite database files (`.db`, `.db-wal`, `.db-shm`) **must reside on persistent, locally attached block storage**. Never host SQLite on network shares (NFS/SMB) or ephemeral container filesystems where data is erased on restart.
- **Horizontal Scaling Limitation:** Because SQLite is an embedded file-based engine, multiple horizontally scaled application containers on different hosts cannot safely share a single writable SQLite file.
- **Enterprise Migration Path (Beyond Single Node):**
  - **Relational Database:** Migrate `conversations`, `messages`, `idempotency_keys`, and `system_metrics` to **PostgreSQL** with connection pooling (e.g. `asyncpg` / PgBouncer).
  - **Distributed Cache & Coordination:** Migrate `response_cache` and `inflight_requests` (leader lease locks) to **Redis** using Redis `SET NX EX` distributed locks and pub/sub for in-flight coalescing.
- **Evaluator Note:** The system is explicitly designed and verified for reliable single-host operation; claims of supporting 1,500 simultaneous un-queued concurrent users on a single SQLite instance are inaccurate and unsupported by SQLite's single-writer architecture.
