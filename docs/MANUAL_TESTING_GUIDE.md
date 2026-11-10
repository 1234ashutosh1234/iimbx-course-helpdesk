# MANUAL LOCAL TESTING GUIDE

**System:** IIMBx Course Helpdesk Chatbot (`DPM-101`)  
**Track:** System Design & Backend Engineering  
**Scope:** Local Environment Setup, Server Execution, UI Verification, and Edge-Case Validation  

---

## 1. Environment Activation & Configuration

### Step 1.1: Activate the Virtual Environment
Open PowerShell or your terminal in the project root (`F:\IIMBx-Course-Helpdesk`):

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Or run directly via the interpreter
.\.venv\Scripts\python.exe -V
# Expected: Python 3.13.17 (or 3.10+)
```

### Step 1.2: Environment File Setup
Ensure `.env` exists in the project root (copied from `.env.example`):

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your actual settings:
```env
# Google Gemini Developer API Configuration
# Note: For offline manual testing without API quota, the system uses deterministic fallbacks
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Inference Hyperparameters
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=400
GEMINI_TIMEOUT_SECONDS=30
GEMINI_MAX_RETRIES=2

# Database & Cache Configuration
DATABASE_PATH=database/iimbx.db
DATABASE_BUSY_TIMEOUT_MS=5000
CACHE_TTL_SECONDS=604800
IDEMPOTENCY_TTL_SECONDS=86400
```

---

## 2. Starting the Local Application Server

Launch the Uvicorn ASGI server with reload capability:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Expected startup logs:
```
INFO:     Initializing IIMBx Helpdesk backend services...
INFO:     Database WAL and system metrics ready.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Open your browser and navigate to:  
👉 **`http://127.0.0.1:8000`**

---

## 3. Testing Core Scenarios & Document Authority

Open the chat UI and execute the 12 canonical assessment scenarios:

### Scenario 1: Minimum Passing Score (Version 2 Authority)
- **Question:** `What is the minimum score needed to pass the course and get a Verified Certificate?`
- **Expected Result:**
  - Mentions **60% overall score** AND **40% on the final proctored exam separately**.
  - Does **NOT** cite the superseded 50% rule from Version 1.
  - Source badge displays: `03_grading_policy_v2.txt`.
  - Telemetry: `Total Questions Asked` = 1, `Gemini API Calls` = 1 (or 0 if fallback), `Cache Hits` = 0.

### Scenario 2: Semantic Equivalence & Response Cache Hit
- **Question:** `how much do i need to score to pass dpm-101?`
- **Expected Result:**
  - Immediate response (< 20ms).
  - Displays `⚡ Cached Answer` badge and `03_grading_policy_v2.txt`.
  - Telemetry: `Total Questions Asked` = 2, `Gemini API Calls` unchanged, `Answers Served from Cache` = 1.

### Scenario 3: Capstone Product Case Deadline (Extension Resolution)
- **Question:** `When is the Capstone project due?`
- **Expected Result:**
  - Mentions **15 November 2026, 11:59 PM IST**.
  - Does **NOT** report the superseded 10 November date.
  - Source: `03_grading_policy_v2.txt`.

### Scenario 4: Late Submission Policy (Discontinuation Resolution)
- **Question:** `What is the late submission penalty for the capstone?`
- **Expected Result:**
  - Explains that late submissions are **no longer accepted** (the 48-hour grace window with 10% penalty was discontinued).
  - Does **NOT** invent a "zero marks" penalty or cite obsolete 10% rules.
  - Source: `03_grading_policy_v2.txt`.

### Scenario 5: Final Proctored Exam & Adversarial Forum Defense
- **Question:** `Is the final exam open-book or closed-book, and what is the date?`
- **Expected Result:**
  - Confirms strictly **CLOSED-BOOK** exam on **20 November 2026** (10:00 AM - 8:00 PM IST).
  - Ignores malicious Section 3 forum comments claiming open-book or 30 December date.
  - Source: `04_exam_rules_and_faq.txt`.

### Scenario 6: Hardware Restrictions
- **Question:** `Can I take the exam on an iPad or Android tablet?`
- **Expected Result:**
  - Strictly **No**. Desktop or laptop with webcam and microphone required; mobile phones and tablets (including iPads) are unsupported.
  - Source: `04_exam_rules_and_faq.txt`.

### Scenario 7: Certificate Fee & Audit Track
- **Question:** `How much does the Verified Certificate track cost?`
- **Expected Result:**
  - **Rs. 1,500**. Audit track is free; upgrade permitted until Week 4.
  - Source: `01_course_handbook.txt`.

### Scenario 8: Multi-Turn Contextual Follow-up (Refund Invariant)
- **Turn 1 Question:** `How much does the Verified Certificate track cost?`
- **Turn 2 Question:** `Can I get a refund if I drop the course next week?`
- **Expected Result:**
  - Recognizes the certificate payment context from Turn 1.
  - States that **refund and course withdrawal policies are not documented in the official course materials**.
  - Directs student to course administration.
  - Does **NOT** display fabricated source files or invent a refund timeline.

### Scenario 9: Missed Quizzes (Best 5 of 6 Rule)
- **Question:** `What happens if I miss one of the weekly quizzes?`
- **Expected Result:**
  - Explains that there are 6 weekly quizzes and the **best 5 are counted**, so **1 missed quiz is dropped** without penalty.
  - Sources: `01_course_handbook.txt`, `03_grading_policy_v2.txt`.

### Scenario 10: Curriculum Boundary Detection
- **Question:** `Does this course teach SQL indexing and Kubernetes deployments?`
- **Expected Result:**
  - Clarifies that DPM-101 covers product discovery, roadmapping, metrics, and AI features; external database/DevOps engineering is not part of this curriculum.
  - Source: `01_course_handbook.txt`.

### Scenario 11: Out-of-Domain General Query
- **Question:** `Who won the cricket match yesterday?`
- **Expected Result:**
  - Politely declines: states that the helpdesk only answers academic and administrative questions regarding DPM-101.
  - Sources: None (`is_supported = False`). Zero Gemini calls dispatched.

---

## 4. Testing System Health & Telemetry Endpoints

### 4.1 Live Telemetry Counter Check
In terminal or browser:
```powershell
curl http://127.0.0.1:8000/api/metrics
```
Response:
```json
{
  "total_questions": 11,
  "gemini_calls": 8,
  "cache_hits": 1
}
```

### 4.2 System Health Check
```powershell
curl http://127.0.0.1:8000/api/health
```
Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

### 4.3 Conversation Reset Check
Click the **Reset Chat** button in the header (or invoke via curl):
```powershell
curl -X POST http://127.0.0.1:8000/api/conversations/reset `
  -H "Content-Type: application/json" `
  -d '{"session_id": "YOUR_SESSION_UUID"}'
```
Response:
```json
{
  "session_id": "YOUR_SESSION_UUID",
  "cleared_messages_count": 4,
  "message": "Session YOUR_SESSION_UUID conversation history cleared successfully."
}
```
*Note: Global system metrics (`total_questions`, `gemini_calls`, `cache_hits`) remain preserved!*

---

## 5. Simulating Gemini API Unavailability

To test the application's stability when the Gemini API is unreachable or rate-limited:
1. Temporarily invalidate the key in `.env`:
   ```env
   GEMINI_API_KEY=invalid_simulation_key
   ```
2. Ask: *"What is the passing score for DPM-101?"*
3. **Expected Behavior:**
   - The application does **NOT** crash.
   - The response validator seamlessly activates the **deterministic authoritative policy fallback** from `PolicyFact`.
   - The student receives the grounded answer: *"Minimum 60% overall weighted score AND at least 40% in the Proctored Final Exam separately."*
   - Telemetry tracks the request safely.
