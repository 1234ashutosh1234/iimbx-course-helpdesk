# SUBMISSION CHECKLIST & VERIFICATION MATRIX

**Project:** IIMBx Course Helpdesk Chatbot (DPM-101)  
**Track:** System Design & Backend  
**Assessment Target:** IIMBx Internship Technical Assessment  
**Evaluation Date:** October/November 2026  
**Final Automated Test Status:** 138/138 Passing (100%)  

---

## 1. Compliance with Assessment Brief Requirements

| # | Assessment Requirement | Project Implementation | Verification / Traceability | Status |
| :-: | :--- | :--- | :--- | :-: |
| **1** | **Preserve Course Documents** | Original files in `course_docs/` kept 100% unaltered. Document quirks handled purely in software logic. | Verified via SHA-256 hash audit against initial inspection. | **PASS** |
| **2** | **Document Authority Hierarchy** | Strict 3-level hierarchy implemented in `backend/knowledge/registry.py` and `resolver.py`. Level 1 active; Level 2 superseded; Level 3 untrusted. | `tests/unit/test_authority.py`, `test_policy_resolver.py` | **PASS** |
| **3** | **Policy Conflict Resolution: Passing Score** | Enforces 60% overall AND 40% exam separately from `03_grading_policy_v2.txt`. Overrides obsolete 50% in v1. | `tests/unit/test_policy_resolver.py::test_passing_criteria_includes_60_and_40` | **PASS** |
| **4** | **Policy Conflict Resolution: Late Submissions** | Enforces "Discontinued — No longer accepted". Does not assume 0 marks or invent numerical penalties. | `tests/unit/test_policy_resolver.py::test_late_submission_discontinued_no_numerical_penalty_invented` | **PASS** |
| **5** | **Policy Conflict Resolution: Capstone Due Date** | Enforces 15 November 2026, 11:59 PM IST from v2. Rejects 10 November from v1. | `tests/unit/test_policy_resolver.py::test_capstone_deadline_is_15_november` | **PASS** |
| **6** | **Exam Guidelines & Device Restrictions** | Enforces 20 November 2026, closed-book, laptop/desktop with webcam only. Rejects iPads/tablets/phones. | `tests/unit/test_policy_resolver.py::test_exam_is_closed_book_and_scheduled_20_november` | **PASS** |
| **7** | **Adversarial Prompt Injection Defense** | Section 3 forum comments completely excluded from policy retrieval. Learner_819 claims ignored. | `tests/unit/ai/test_prompts.py::test_forum_injection_never_reaches_prompt` | **PASS** |
| **8** | **Unsupported Queries (Graceful Degradation)** | Transparently reports lack of documentation for refunds, SQL, Kubernetes, and off-topic questions. Bypasses LLM. | `tests/unit/test_retrieval.py::test_retrieval_for_refund_policy_returns_unsupported` | **PASS** |
| **9** | **Modern Google Gemini SDK** | Implemented with official `google-genai` SDK (v3.0.0+). No deprecated legacy libraries used. | `backend/ai/gemini_client.py`, `requirements.txt` | **PASS** |
| **10** | **Configurable Gemini Model** | Default `gemini-3.8-flash`, configurable via `GEMINI_MODEL` environment variable. | `backend/config.py`, `render.yaml` | **PASS** |
| **11** | **Structured Answer Generation** | Pydantic JSON schema output with factual anchor validation and deterministic policy fallback. | `backend/ai/answer_generator.py`, `backend/ai/response_validator.py` | **PASS** |
| **12** | **SQLite WAL Database Architecture** | High-concurrency SQLite with WAL mode, busy timeout (5000ms), and startup migrations. | `backend/database/connection.py`, `backend/database/migrations.py` | **PASS** |
| **13** | **Response Caching Engine** | Normalized SHA-256 query hashing with corpus and prompt versioning. Caches only grounded answers. | `backend/services/cache_service.py` | **PASS** |
| **14** | **Idempotency & Concurrency Coordination** | `X-Idempotency-Key` handling with leader-follower in-flight request locking and HTTP 202 coordination. | `backend/services/idempotency.py`, `backend/services/chat_service.py` | **PASS** |
| **15** | **Atomic Telemetry Counters** | Three live counters updated using atomic SQL expressions (`metric_value = metric_value + 1`). | `backend/services/metrics_service.py` | **PASS** |
| **16** | **FastAPI Backend Endpoints** | REST API endpoints `/api/chat`, `/api/metrics`, `/api/health`, `/api/conversations/reset`. | `backend/api/routes/` | **PASS** |
| **17** | **Vanilla Frontend Web Interface** | Semantic HTML5, CSS3, ES6 JS. Zero external build tools. Live telemetry, backend health indicator, prototype banner. | `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/` | **PASS** |
| **18** | **Render Cloud Deployment** | Ready-to-deploy `render.yaml` blueprint with ephemeral storage documentation and `/tmp` database path. | `render.yaml`, `docs/DEPLOYMENT_GUIDE.md` | **PASS** |
| **19** | **Security & Secret Sanitization** | `.env` excluded from git; zero hardcoded secrets; XSS-safe DOM rendering (`textContent`). | `tests/api/test_api_security.py` | **PASS** |
| **20** | **Automated Test Coverage** | 138 passing automated tests covering all modules offline without live token consumption. | `pytest -v tests/` (138/138 passed) | **PASS** |

---

## 2. Deliverables Checklist

- [x] **Source Code:** Complete modular backend and frontend in repository root.
- [x] **Course Documents (Unaltered):**
  - `course_docs/01_course_handbook.txt`
  - `course_docs/02_grading_policy_v1.txt`
  - `course_docs/03_grading_policy_v2.txt`
  - `course_docs/04_exam_rules_and_faq.txt`
- [x] **Assessment Specification:**
  - `reference/SD_Assessment.docx`
  - `tests/fixtures/sample_test_questions.txt`
- [x] **Production Infrastructure & Config:**
  - `render.yaml`
  - `.python-version`
  - `requirements.txt`
  - `.env.example`
  - `.gitignore`
- [x] **Engineering Documentation:**
  - `README.md`
  - `docs/ARCHITECTURE.md`
  - `docs/ASSESSMENT_ANALYSIS.md`
  - `docs/GEMINI_INTEGRATION.md`
  - `docs/DATABASE_AND_CACHING.md`
  - `docs/API_REFERENCE.md`
  - `docs/MANUAL_TESTING_GUIDE.md`
  - `docs/TEST_MATRIX.md`
  - `docs/DEPLOYMENT_GUIDE.md`
  - `docs/SUBMISSION_CHECKLIST.md` (this file)
  - `AGENTS.md`
- [x] **Automated Tests:**
  - 138 automated unit, security, caching, concurrency, and API integration tests in `tests/`.

---

## 3. Evaluator Submission Steps

For the candidate submitting to the IIMBx evaluator:

1. **Push to Public GitHub Repository:**
   ```bash
   git add .
   git commit -m "feat: complete IIMBx course helpdesk chatbot submission"
   git push origin main
   ```
2. **Deploy on Render (or alternative platform):**
   * Follow `docs/DEPLOYMENT_GUIDE.md` to deploy via Blueprint or Web Service.
   * Enter your `GEMINI_API_KEY` in Render environment variables.
3. **Verify Public URL:**
   * Test public endpoint `/api/health` returns HTTP 200 `{"status": "healthy"}`.
   * Open the frontend in your browser and test the sample questions.
4. **Submit Links:**
   * **GitHub Repository URL:** `https://github.com/<your-username>/IIMBx-Course-Helpdesk`
   * **Live Chatbot URL:** `https://<your-render-service>.onrender.com`
   * **README & Documentation:** Point evaluators to `README.md` for complete testing and architecture details.
