# API REFERENCE SPECIFICATION

**System:** IIMBx Course Helpdesk Chatbot (`DPM-101`)  
**Track:** System Design & Backend Architecture  
**Base URL:** `http://127.0.0.1:8000` (Local) / Production Hosting URL  
**Version:** `1.0.0`  

---

## 1. Global Architectural & Security Standards

- **Idempotency Protection:** The chat endpoint accepts an `X-Idempotency-Key: UUID` header. Duplicate requests with the same key and payload replay the existing response without incrementing counters or calling the LLM.
- **Content Types:** All request and response bodies use `application/json` (UTF-8 encoded), except `GET /` which serves `text/html`.
- **Security Response Headers:**
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Error Format:** All API errors return structured JSON with an `error` category and a descriptive, non-leaking `detail` string.

---

## 2. Endpoints Specification

### 2.1 Serve Frontend Dashboard
`GET /`

Serves the official university course helpdesk web user interface.

- **Request:** None
- **Response Headers:** `Content-Type: text/html; charset=utf-8`
- **Status Codes:**
  - `200 OK`: Successful retrieval of `frontend/index.html`.
  - `404 Not Found`: Frontend asset directory missing.

---

### 2.2 Student Chat & Policy Inquiry
`POST /api/chat`

Processes a student question through deterministic policy retrieval, response caching, in-flight coordination, and Gemini AI answer generation.

#### Request Headers:
| Header | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `Content-Type` | `string` | **Yes** | Must be `application/json` |
| `X-Idempotency-Key` | `string (UUID)` | Optional | Unique client-generated UUID token for double-click and replay deduplication. If omitted, the server automatically generates one. |

#### Request Body:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What is the minimum score needed to pass DPM-101?"
}
```

| Field | Type | Validation Rules | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | `string` | Valid UUID format (`RFC 4122`) | Identifies the student's conversation thread across turns. |
| `message` | `string` | Min: 1 character, Max: 1,000 characters | Raw student question text. Whitespace is stripped. |

#### Success Response (`200 OK`):
```json
{
  "answer": "To earn a Verified Certificate, learners must achieve an overall weighted score of at least 60% across quizzes, the capstone case, and the final exam, AND obtain at least 40% on the Proctored Final Exam separately.",
  "sources": [
    "03_grading_policy_v2.txt",
    "01_course_handbook.txt"
  ],
  "is_supported": true,
  "served_from_cache": false,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "metrics": {
    "total_questions": 1,
    "gemini_calls": 1,
    "cache_hits": 0
  }
}
```

| Response Field | Type | Description |
| :--- | :--- | :--- |
| `answer` | `string` | Conversational answer grounded strictly in active course documents. |
| `sources` | `array[string]` | Official filenames containing the supporting evidence (never fabricated). |
| `is_supported` | `boolean` | `true` if policy is covered; `false` if query is out-of-scope (e.g. refunds, cricket). |
| `served_from_cache` | `boolean` | `true` if answer was served directly from persistent SQLite WAL cache. |
| `session_id` | `string` | Echoed session UUID. |
| `metrics` | `object` | Current snapshot of system counters after processing this request. |

#### In-Progress Response (`202 Accepted`):
Returned when another concurrent worker is actively generating the answer for the same request fingerprint:
```json
{
  "answer": "Request currently being processed. Please refresh in a moment.",
  "sources": [],
  "is_supported": false,
  "served_from_cache": false,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "metrics": {
    "total_questions": 1,
    "gemini_calls": 0,
    "cache_hits": 0
  }
}
```
- **Header:** `Retry-After: 1`

#### Error Responses:
- **`409 Conflict` (Idempotency Key Reuse Conflict):**
  ```json
  {
    "error": "Idempotency Conflict",
    "detail": "Idempotency key '...' was previously registered with a different request payload."
  }
  ```
- **`422 Unprocessable Content` (Validation Failure):**
  ```json
  {
    "error": "Validation Error",
    "detail": "Invalid request parameters or payload format."
  }
  ```
- **`500 Internal Server Error` (Unexpected Server Failure):**
  ```json
  {
    "error": "Internal Server Error",
    "detail": "An error occurred while generating your course assistance response. Please try again."
  }
  ```

---

### 2.3 Live System Telemetry Metrics
`GET /api/metrics`

Returns live atomic counters from SQLite `system_metrics`.

- **Request:** None
- **Response (`200 OK`):**
```json
{
  "total_questions": 42,
  "gemini_calls": 25,
  "cache_hits": 17
}
```

| Metric Field | Definition |
| :--- | :--- |
| `total_questions` | Total accepted unique logical student questions (idempotency replays do NOT increment). |
| `gemini_calls` | Actual outbound HTTP API dispatches made to Google Gemini (including retries). |
| `cache_hits` | Grounded answers resolved from persistent SQLite response cache. |

---

### 2.4 Service Health Check
`GET /api/health`

Performs non-destructive health and database availability check.

- **Request:** None
- **Response (`200 OK`):**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```
- **Response (`503 Service Unavailable`):**
```json
{
  "status": "degraded",
  "database": "unavailable",
  "version": "1.0.0"
}
```
*Note: This endpoint executes `SELECT 1;` against SQLite and never invokes Gemini.*

---

### 2.5 Conversation Session Reset
`POST /api/conversations/reset`

Clears message history for a student's specific session thread.

#### Request Body:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Success Response (`200 OK`):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "cleared_messages_count": 6,
  "message": "Session 550e8400-e29b-41d4-a716-446655440000 conversation history cleared successfully."
}
```

#### Safety Guarantees:
- Only deletes rows from `messages` where `session_id = ?`.
- Never affects other students' sessions.
- Never touches global `system_metrics`.

---

## 3. Status Codes Summary

| HTTP Status | Meaning | Typical Occurrence |
| :--- | :--- | :--- |
| **`200 OK`** | Success | Chat response, metrics, health, reset |
| **`202 Accepted`** | In Progress | Concurrent leader generation in-flight |
| **`404 Not Found`** | Not Found | Route does not exist |
| **`409 Conflict`** | Conflict | Reusing idempotency key with different payload |
| **`422 Unprocessable`** | Validation Error | Malformed UUID, empty text, or > 1,000 characters |
| **`500 Internal Error`**| Server Error | Handled gracefully without stack trace leakage |
| **`503 Unavailable`** | Service Down | Database connectivity failure on `/api/health` |
