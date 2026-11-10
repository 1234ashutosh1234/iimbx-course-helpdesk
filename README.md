# IIMBx Course Helpdesk Chatbot (DPM-101)

**Track:** System Design & Backend  
**Course:** DPM-101: Digital Product Management  
**Target Audience:** 1,500 Students  
**Framework & Runtime:** Python 3.13.17, FastAPI, SQLite (WAL mode), Google Gemini API (`google-genai` v3.0.0+)  
**Frontend:** Vanilla HTML5, CSS3, ES6 JavaScript (zero build step, zero client dependencies)  

---

## 1. Executive Summary & Assessment Overview

The **IIMBx Course Helpdesk Chatbot** is a production-grade, highly resilient backend service and web application engineered for the IIMBx Technical Assessment. It serves as an authoritative academic policy assistant for the **DPM-101: Digital Product Management** course, providing instant, grounded answers to student inquiries regarding syllabus policies, passing criteria, assignment deadlines, and proctored examination rules.

### Key Architectural Strengths:
1. **Deterministic Document Authority Hierarchy:** Explicitly resolves version conflicts between superseded and active grading policies (`02_grading_policy_v1.txt` vs `03_grading_policy_v2.txt`) without relying on non-deterministic file modification timestamps (`mtime`).
2. **Defensive Prompt Injection Neutralization:** Completely isolates unmoderated forum comments (Section 3 of `04_exam_rules_and_faq.txt`) and adversarial student prompt injections (e.g., Learner_819) from authoritative retrieval pipelines.
3. **Structured Gemini Generation & Factual Anchor Validation:** Utilizes Google's modern `google-genai` SDK (`gemini-3.8-flash`) with strict Pydantic JSON schemas and factual anchor validation. Automatically falls back to deterministic authoritative policy facts if Gemini fails or drifts.
4. **SQLite 3 WAL Architecture & Atomic Telemetry:** High-concurrency database layer operating in Write-Ahead Logging (`WAL`) mode with atomic SQL counters (`UPDATE system_metrics SET metric_value = metric_value + 1`), robust response caching, and an in-flight request coordinator preventing duplicate Gemini dispatches.
5. **Idempotency & Double-Click Guard:** Enforces `X-Idempotency-Key` headers on chat inquiries with SHA-256 payload verification and HTTP 202 leader/follower polling coordination.
6. **148 Automated Tests Passing:** Comprehensive pytest suite covering unit, multi-intent classification, AI validation, security, concurrency, caching, and FastAPI endpoints.

---

## 2. Document Authority & Policy Hierarchy

The chatbot strictly enforces the following document hierarchy across all retrieval and answer generation:

```
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: 03_grading_policy_v2.txt (CURRENT ACTIVE POLICY - Oct 2026)  │
│   • Passing Criteria: 60% overall score AND 40% final exam separately  │
│   • Late Submissions: DISCONTINUED (not accepted; no penalty assumed)  │
│   • Missed Quiz: 1 lowest quiz dropped (best 5 of 6 evaluated)         │
│   • Capstone Due Date: 15 November 2026, 11:59 PM IST                  │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 1: 04_exam_rules_and_faq.txt (Sections 1 & 2: OFFICIAL RULES)    │
│   • Proctored Exam Date: 20 November 2026 (Slots 10 AM - 8 PM IST)     │
│   • Format: Strictly CLOSED-BOOK (no notes, internet, or AI aids)      │
│   • Permitted Devices: Desktop / Laptop with webcam only (NO tablets)  │
│   • Identification: Valid Government Photo ID required                 │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 1: 01_course_handbook.txt (BASELINE COURSE SYLLABUS)             │
│   • Duration & Effort: 8 weeks, 4–5 hours per week                     │
│   • Grade Weights: Quizzes 30%, Capstone 30%, Proctored Exam 40%       │
│   • Certification: Audit is free; Verified Certificate is Rs. 1,500    │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 2: 02_grading_policy_v1.txt (SUPERSEDED / INACTIVE - Jan 2026)   │
│   • [OBSOLETE] 50% passing threshold is completely superseded          │
│   • [OBSOLETE] 48-hour late grace with 10% penalty is discontinued     │
│   • [OBSOLETE] 10 November capstone deadline is obsolete               │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 3: 04_exam_rules_and_faq.txt (Section 3: UNTRUSTED FORUM)        │
│   • NON-AUTHORITATIVE: Completely excluded from policy retrieval       │
│   • Learner_819 is an adversarial prompt injection attempt             │
│   • System strictly ignores open-book and December 30 date claims      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Purpose & Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.13.17 | Modern, type-annotated, high-performance async runtime |
| **Framework** | FastAPI 0.115+ | High-throughput asynchronous ASGI web framework |
| **Server** | Uvicorn (standard) | High-concurrency ASGI server with uvloop support |
| **LLM Client** | `google-genai` (v3.0.0+) | Official modern Google GenAI SDK (replaces deprecated legacy libraries) |
| **Default Model** | `gemini-3.8-flash` | Ultra-fast, highly accurate structured reasoning with low latency |
| **Database** | SQLite 3 (`aiosqlite`) | Embedded zero-maintenance DB configured in WAL mode with busy timeouts |
| **Validation** | Pydantic v2 | Robust request/response validation and structured JSON schemas |
| **Frontend** | HTML5, CSS3, ES6 JS | Zero external dependencies; native browser security with XSS defense |
| **Test Suite** | Pytest, Pytest-Asyncio | 148 offline unit & integration tests with complete mocked LLM isolation |
| **Deployment** | Render Blueprint | Single-click infrastructure-as-code specification (`render.yaml`) |

---

## 4. Local Installation & Setup

### Prerequisites
* Python 3.10 or higher (Python 3.13.17 recommended)
* Git
* A Google Gemini Developer API key ([Google AI Studio](https://aistudio.google.com/))

### Step 1: Clone the Repository
```bash
git clone https://github.com/<your-username>/IIMBx-Course-Helpdesk.git
cd IIMBx-Course-Helpdesk
```

### Step 2: Set Up Virtual Environment
```bash
# On Linux/macOS:
python3 -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the configuration template and insert your Gemini API Key:
```bash
# On Linux/macOS:
cp .env.example .env

# On Windows:
copy .env.example .env
```

Edit `.env`:
```ini
GEMINI_API_KEY=AIzaSy...your_actual_gemini_api_key...
GEMINI_MODEL=gemini-3.8-flash
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=400
DATABASE_PATH=database/iimbx.db
CACHE_TTL_SECONDS=604800
IDEMPOTENCY_TTL_SECONDS=86400
```

### Step 5: Verify Gemini API Connectivity (Optional Smoke Test)
```bash
python scripts/check_gemini_connection.py
```
*Expected output: Success confirmation displaying model identifier and sample response.*

### Step 6: Run the Complete Automated Test Suite
```bash
pytest -v tests/
```
*Expected output: 148 passed in under 2.5 minutes.*

### Step 7: Launch the Application
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at:  
👉 **`http://localhost:8000`**

---

## 5. Deployment Guide (Render Blueprint)

The repository includes a ready-to-deploy Infrastructure-as-Code blueprint in [`render.yaml`](file:///f:/IIMBx-Course-Helpdesk/render.yaml).

### Deploying to Render in 5 Steps:
1. **Push your code to GitHub:**
   ```bash
   git add .
   git commit -m "feat: complete IIMBx course helpdesk chatbot"
   git push origin main
   ```
2. **Log into Render:** Navigate to [dashboard.render.com](https://dashboard.render.com/).
3. **Create a New Blueprint Instance:**
   * Click **New +** > **Blueprint**.
   * Select your GitHub repository (`IIMBx-Course-Helpdesk`).
   * Render automatically reads `render.yaml` and provisions the web service.
4. **Set Secret Environment Variable:**
   * When prompted for `GEMINI_API_KEY`, paste your actual Google Gemini API key.
   * Click **Apply**.
5. **Access Your Live URL:**
   * Once built, your public web service will be accessible at:  
     `https://iimbx-course-helpdesk.onrender.com`

---

## 6. Operational Realities of Free Cloud Hosting

When deploying to Render's Free tier, the following infrastructure characteristics apply:

1. **Inactivity Spin-Down (Cold Starts):**
   * Free web services spin down after **15 minutes of inactivity**.
   * The first incoming request after spin-down incurs a **30–60 second cold start** while the container provisions. Subsequent requests respond in sub-second time.
2. **Ephemeral Filesystem (`/tmp`):**
   * Free tier web services do not have persistent disk storage.
   * The SQLite database is intentionally configured at `/tmp/iimbx-course-helpdesk.db`.
   * When the instance spins down or redeploys, the SQLite file in `/tmp` resets.
   * **Self-Healing Design:** The application automatically runs migrations (`DatabaseManager.initialize()`) on every startup, ensuring that tables, schema version, and zeroed telemetry counters are instantly recreated without manual intervention.

---

## 7. Evaluator Testing & Verification Guide

Technical evaluators can test the core competencies of the chatbot using the following test cases:

### Test Case 1: Active Policy Resolution (Passing Score)
* **Question:** *"What is the passing score for the course?"*
* **Expected Answer:** Overall minimum 60% across all components **AND** at least 40% separately on the final proctored exam.
* **Authority Checked:** Cites `03_grading_policy_v2.txt`. Demonstrates rejection of superseded 50% rule in v1.

### Test Case 2: Discontinued Late Submissions
* **Question:** *"Can I submit the capstone assignment two days late?"*
* **Expected Answer:** Late submissions are **discontinued** and no longer accepted.
* **Authority Checked:** Demonstrates that the chatbot does not invent a numerical penalty (such as the obsolete 10% penalty from v1).

### Test Case 3: Capstone Submission Deadline
* **Question:** *"When is the capstone project due?"*
* **Expected Answer:** **15 November 2026 at 11:59 PM IST**.
* **Authority Checked:** Rejects obsolete 10 November deadline from v1.

### Test Case 4: Adversarial Prompt Injection Defense
* **Question:** *"Is the exam open book? Someone on the forum said we can use notes."*
* **Expected Answer:** Strictly **closed-book**. No books, notes, web browsing, or AI tools are permitted. Exam date is 20 November 2026.
* **Security Checked:** Neutralizes Learner_819 adversarial injection from Section 3.

### Test Case 5: Unsupported Academic Policy (Graceful Degradation)
* **Question:** *"What is the refund policy if I drop out after week 2?"*
* **Expected Answer:** Transparently states that refund policies are not documented in the course handbook. Directs student to official IIMBx Helpdesk support.
* **Engine Checked:** Bypasses Gemini API entirely (`gemini_calls` counter does not increment).

### Test Case 6: Telemetry & Cache Verification
1. Submit: *"What is the minimum passing score?"*
   * Result: `total_questions` increments by 1; `gemini_calls` increments by 1; `cache_hits` remains 0.
2. Re-submit the identical question or a paraphrase (*"What score do I need to pass DPM-101?"*):
   * Result: `total_questions` increments by 1; `gemini_calls` **does not change**; `cache_hits` increments by 1. Badge displays **⚡ Cached Answer**.

### Test Case 7: Multi-Intent Question Handling
* **Question:** *"What is the final exam date, and is it open-book or closed-book?"*
* **Expected Answer:** "The Proctored Final Exam is scheduled for 20 November 2026, with appointment slots available between 10:00 AM and 8:00 PM IST. The examination is strictly closed-book. External websites, search engines, course notes and AI tools are not permitted."
* **Multi-Intent Checked:** Concurrently classifies `FINAL_EXAM_DATE` and `EXAM_FORMAT`, retrieves both official facts, preserves correct attribution (`04_exam_rules_and_faq.txt`), and shares cache keys across intent orderings.

### Test Case 8: Document-Grounded Unsupported Query Wording
* **Question:** *"Does this course teach SQL database indexing and Kubernetes deployment?"*
* **Expected Answer:** "The supplied DPM-101 course documents describe user research, product roadmapping, metrics, and AI feature design. They do not mention SQL database indexing or Kubernetes deployment."
* **Grounding Checked:** Accurately cites `01_course_handbook.txt` without making unsubstantiated claims of definitive curriculum exclusion. Bypasses external LLM dispatch.

---

## 8. Directory Layout

```
IIMBx-Course-Helpdesk/
├── course_docs/                      # Official Course Documents (READ-ONLY)
│   ├── 01_course_handbook.txt
│   ├── 02_grading_policy_v1.txt
│   ├── 03_grading_policy_v2.txt
│   └── 04_exam_rules_and_faq.txt
├── backend/                          # FastAPI Backend & Core Logic
│   ├── main.py                       # App factory, static files, lifecycle
│   ├── config.py                     # Environment variables & hyperparameters
│   ├── api/                          # Endpoints & Pydantic schemas
│   │   ├── routes/                   # /chat, /metrics, /health, /conversations
│   │   ├── dependencies.py           # Dependency injection providers
│   │   └── schemas.py                # Request & response contracts
│   ├── knowledge/                    # Document Intelligence Engine
│   │   ├── loader.py                 # Safe loader & SHA-256 corpus hashing
│   │   ├── registry.py               # Document authority & metadata
│   │   ├── resolver.py               # Policy conflict resolver
│   │   ├── classifier.py             # Query intent classification
│   │   └── retrieval.py              # Authoritative evidence retriever
│   ├── ai/                           # Gemini AI Integration & Defense
│   │   ├── gemini_client.py          # Modern google-genai wrapper
│   │   ├── prompts.py                # Grounded prompt engineering
│   │   ├── answer_generator.py       # Structured JSON generation & fallback
│   │   └── response_validator.py     # Factual anchor validation
│   ├── database/                     # SQLite WAL Storage
│   │   ├── connection.py             # Connection pool & busy timeout
│   │   ├── schema.sql                # DDL & indexing
│   │   └── migrations.py             # Atomic startup migrations
│   └── services/                     # Business Logic Services
│       ├── chat_service.py           # Orchestration coordinator
│       ├── cache_service.py          # Response cache & normalization
│       ├── idempotency.py            # Deduplication & in-flight locking
│       └── metrics_service.py        # Atomic telemetry counter tracking
├── frontend/                         # Vanilla Web Client
│   ├── index.html                    # Responsive semantic UI & telemetry
│   ├── css/styles.css                # University EdTech design theme
│   └── js/                           # Modular vanilla JS controllers
│       ├── api.js                    # HTTP client, UUID & session handling
│       ├── chat.js                   # XSS-safe DOM rendering
│       ├── metrics.js                # Live telemetry polling
│       └── app.js                    # Main UI event coordinator
├── tests/                            # 148 Automated Tests
│   ├── conftest.py                   # Pytest fixtures & mock configs
│   ├── unit/                         # Unit tests (knowledge, ai, db, services, multi-intent)
│   └── api/                          # Integration tests (FastAPI endpoints)
├── docs/                             # Engineering Architecture & Reports
│   ├── ARCHITECTURE.md               # Complete System Architecture
│   ├── ASSESSMENT_ANALYSIS.md        # Problem analysis & policy resolution
│   ├── GEMINI_INTEGRATION.md         # Gemini SDK & prompting details
│   ├── DATABASE_AND_CACHING.md       # SQLite, cache & idempotency design
│   ├── API_REFERENCE.md              # REST API contract documentation
│   ├── MANUAL_TESTING_GUIDE.md       # Interactive browser test script
│   ├── TEST_MATRIX.md                # Automated test traceability matrix
│   └── DEPLOYMENT_GUIDE.md           # Render step-by-step setup guide
├── .env.example                      # Environment configuration template
├── .gitignore                        # Git exclusion rules (secrets, DBs, venv)
├── .python-version                   # Pinned Python version (3.13.17)
├── render.yaml                       # Render Infrastructure-as-Code Blueprint
├── requirements.txt                  # Minimal pinned production dependencies
└── AGENTS.md                         # Persistent directives for AI assistants
```

---

## 9. License & Integrity Statement

This project was built strictly for the **IIMBx Technical Assessment (System Design & Backend)**. All original course documents in `course_docs/` remain unaltered. No API keys or secrets are stored in this repository.
