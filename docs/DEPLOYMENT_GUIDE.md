# DEPLOYMENT GUIDE — Render Cloud Hosting

**Project:** IIMBx Course Helpdesk Chatbot (DPM-101)  
**Track:** System Design & Backend  
**Deployment Target:** Render (Web Service / Blueprint)  
**Python Runtime:** 3.13.17  
**ASGI Server:** Uvicorn  

---

## 1. Overview & Architecture on Render

The IIMBx Course Helpdesk Chatbot is designed as a self-contained, stateless web service with embedded SQLite WAL storage. It does not require external database instances or complex container registries.

When deployed to Render, the application runs as a native Python web service managed via Render's infrastructure blueprint (`render.yaml`).

```
┌────────────────────────────────────────────────────────┐
│ Render Free Web Service (Linux Container)              │
│                                                        │
│  [ Uvicorn ASGI Server ] (Listening on 0.0.0.0:$PORT) │
│            │                                           │
│            ▼                                           │
│     [ FastAPI Core ]                                   │
│     ├── Static HTML/CSS/JS frontend (served at /)      │
│     ├── REST API (/api/chat, /metrics, /health)        │
│     │                                                  │
│     ├── SQLite WAL Database (/tmp/iimbx-...db)         │
│     │   (Self-initializing schema & telemetry)        │
│     │                                                  │
│     └── Google GenAI Client (Outbound HTTPS)           │
│         └── Google Gemini API (gemini-3.8-flash)       │
└────────────────────────────────────────────────────────┘
```

---

## 2. Deploying via Render Blueprint (Recommended)

Render Blueprints allow infrastructure-as-code deployment directly from the repository's `render.yaml`.

### Step 1: Push Repository to GitHub
Ensure all code and configuration files are pushed to your GitHub repository:
```bash
git add .
git commit -m "feat: add Render deployment blueprint and documentation"
git push origin main
```

### Step 2: Open Render Dashboard
1. Log into [Render Dashboard](https://dashboard.render.com/).
2. In the top right corner, click **New +** and select **Blueprint**.

### Step 3: Connect GitHub Repository
1. Grant Render access to your repository `IIMBx-Course-Helpdesk`.
2. Select the repository from the list.
3. Render will detect `render.yaml` automatically and display the proposed service:
   * **Service Name:** `iimbx-course-helpdesk`
   * **Runtime:** `Python 3`
   * **Plan:** `Free`
   * **Region:** Any (e.g., Oregon, Frankfurt, Singapore)
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Health Check Path:** `/api/health`

### Step 4: Configure the Secret Environment Variable
Render will prompt you for the un-synced secret:
* **`GEMINI_API_KEY`**: Paste your Google Gemini API key obtained from [Google AI Studio](https://aistudio.google.com/).

### Step 5: Deploy
Click **Apply**. Render will:
1. Clone the repository.
2. Install Python dependencies from `requirements.txt`.
3. Launch Uvicorn on the assigned port.
4. Verify `/api/health` responds with HTTP 200.
5. Provide a public URL: `https://iimbx-course-helpdesk.onrender.com`.

---

## 3. Alternative: Manual Web Service Setup

If you prefer to configure the service manually through Render's UI without Blueprint:

1. Click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Fill in the deployment parameters:
   * **Name:** `iimbx-course-helpdesk`
   * **Region:** Choose closest to your evaluators (e.g., Oregon or Frankfurt).
   * **Branch:** `main` (or `master`)
   * **Root Directory:** *(leave blank)*
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Plan Type:** `Free`
4. Expand **Advanced** and set **Health Check Path** to `/api/health`.
5. Add the following **Environment Variables**:
   * `PYTHON_VERSION`: `3.13.17`
   * `GEMINI_MODEL`: `gemini-3.8-flash`
   * `DATABASE_PATH`: `/tmp/iimbx-course-helpdesk.db`
   * `CACHE_TTL_SECONDS`: `604800`
   * `IDEMPOTENCY_TTL_SECONDS`: `86400`
   * `GEMINI_API_KEY`: *(Your secret Gemini API key)*
6. Click **Create Web Service**.

---

## 4. Operational Realities of Render Free Tier

Render Free is an exceptional platform for technical assessment demonstrations, but engineers and evaluators must understand two key operational realities:

### Reality 1: Inactivity Spin-Down (Cold Starts)
* **Behavior:** After 15 minutes of receiving no HTTP traffic, Render automatically spins down free web service instances to conserve cloud resources.
* **Cold Start Latency:** When a new visitor opens the URL, Render provisions and boots the container. This initial request takes **30 to 60 seconds** to respond.
* **Recommendation for Evaluators:** Please allow up to 60 seconds on the first page load. Once awake, the application responds instantly with sub-second latency.

### Reality 2: Ephemeral Disk Storage (`/tmp`)
* **Behavior:** Render Free web services have ephemeral storage. Persistent disks cannot be attached on the Free tier.
* **Configuration:** `DATABASE_PATH` is set to `/tmp/iimbx-course-helpdesk.db` because `/tmp` is guaranteed writable on Linux containers.
* **Reset on Spin-Down:** When an instance spins down after 15 minutes of inactivity or during redeploys, files in `/tmp` are wiped.
* **Self-Healing Design:** The application is architected to handle this gracefully:
  * On every boot, `DatabaseManager.initialize()` executes in `backend/main.py`.
  * It detects if the database file is absent and automatically runs `backend/database/schema.sql`.
  * It creates all required tables (`response_cache`, `idempotency_keys`, `inflight_requests`, `conversation_history`, `system_metrics`).
  * It initializes default telemetry metrics (`total_questions = 0`, `gemini_calls = 0`, `cache_hits = 0`).
  * Telemetry counters are maintained accurately throughout the active session.

---

## 5. Post-Deployment Verification

Once deployed, verify the public service using these checks:

### 1. Health Endpoint Verification
```bash
curl -i https://<your-render-url>.onrender.com/api/health
```
*Expected response:*
```json
{
  "status": "healthy",
  "database": "connected",
  "active_policy": "03_grading_policy_v2.txt",
  "corpus_version": "...",
  "gemini_model": "gemini-3.8-flash"
}
```

### 2. Live Telemetry Verification
```bash
curl -i https://<your-render-url>.onrender.com/api/metrics
```
*Expected response:*
```json
{
  "total_questions": 0,
  "gemini_calls": 0,
  "cache_hits": 0,
  "cache_entries": 0,
  "active_conversations": 0
}
```

### 3. Frontend Verification
Open `https://<your-render-url>.onrender.com` in your web browser:
1. Verify the navy header, IIMBx brand badge, and status dot showing **Backend Connected**.
2. Verify the 3 telemetry counter cards show `0`.
3. Click a starter chip: *"What is the minimum passing score?"*
4. Confirm the assistant responds citing `03_grading_policy_v2.txt` with passing score 60% overall and 40% exam.
5. Confirm the telemetry counters update to `1` total questions and `1` Gemini call.
6. Submit the question again. Confirm the answer is returned instantly with the **⚡ Cached Answer** badge, and the `Answers Served from Cache` counter increments to `1`.

---

## 6. Monitoring & Troubleshooting

### Viewing Render Logs
1. Go to your service on [Render Dashboard](https://dashboard.render.com/).
2. Click the **Logs** tab.
3. Review Uvicorn startup logs:
   ```
   INFO: Database initialized at /tmp/iimbx-course-helpdesk.db (WAL mode)
   INFO: Document intelligence engine ready. Corpus hash: ...
   INFO: Application startup complete.
   INFO: Uvicorn running on http://0.0.0.0:10000
   ```

### Common Issues & Remedies

| Issue | Root Cause | Remedy |
| :--- | :--- | :--- |
| **First request times out or takes 45s** | Service was spun down due to inactivity | Normal Render Free cold start. Wait for initial response; subsequent queries are instantaneous. |
| **HTTP 500 on Gemini query** | `GEMINI_API_KEY` is invalid, missing, or has quota issues | Check Render Environment tab. Ensure `GEMINI_API_KEY` is set correctly. Check Render logs for Google GenAI error messages. |
| **HTTP 409 Conflict** | Same `X-Idempotency-Key` sent with differing prompt payload | Normal idempotency behavior. The client auto-generates a fresh UUID for new queries. |
| **Status indicator shows "Backend Offline"** | FastAPI backend stopped or building | Check Render Logs for unhandled exceptions or build failures. |
