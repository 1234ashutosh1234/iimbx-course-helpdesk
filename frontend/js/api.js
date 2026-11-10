/**
 * API client module for IIMBx Course Helpdesk.
 * Handles HTTP requests, idempotency, retry, and session management.
 */

const ApiClient = (() => {
    const SESSION_STORAGE_KEY = "iimbx_helpdesk_session_id";

    /**
     * Generate a cryptographically strong UUIDv4 string.
     */
    function generateUUID() {
        if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
            return crypto.randomUUID();
        }
        // Fallback for older browsers
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0;
            const v = c === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    /**
     * Retrieve or initialize persistent session UUID from sessionStorage.
     */
    function getSessionId() {
        let sessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (!sessionId) {
            sessionId = generateUUID();
            sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
        }
        return sessionId;
    }

    /**
     * Reset current session by generating a new session UUID.
     */
    function rotateSessionId() {
        const newSessionId = generateUUID();
        sessionStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
        return newSessionId;
    }

    /**
     * Dispatch student chat request to POST /api/chat.
     * Supports automatic Retry-After handling for HTTP 202 in-progress responses.
     */
    async function sendChatMessage(sessionId, message, idempotencyKey = null, attempt = 0) {
        const key = idempotencyKey || generateUUID();

        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Idempotency-Key": key,
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: message.trim(),
            }),
        });

        // Handle HTTP 202: Request currently being processed by concurrent leader
        if (response.status === 202) {
            if (attempt < 4) {
                const retryAfterSec = parseInt(response.headers.get("Retry-After") || "1", 10);
                await new Promise((resolve) => setTimeout(resolve, retryAfterSec * 1000));
                // Retry preserving the exact same idempotency key
                return sendChatMessage(sessionId, message, key, attempt + 1);
            }
            throw new Error("Request is taking longer than expected. Please retry in a moment.");
        }

        // Handle HTTP 409: Idempotency payload conflict
        if (response.status === 409) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || "Idempotency conflict: Key was used with a different request.");
        }

        // Handle validation errors (422) or client errors
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Server returned error (${response.status})`);
        }

        return await response.json();
    }

    /**
     * Fetch live system metrics from GET /api/metrics.
     */
    async function fetchMetrics() {
        const response = await fetch("/api/metrics");
        if (!response.ok) {
            throw new Error("Failed to load telemetry metrics.");
        }
        return await response.json();
    }

    /**
     * Clear message history on the server for the current session.
     */
    async function resetConversation(sessionId) {
        const response = await fetch("/api/conversations/reset", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ session_id: sessionId }),
        });
        if (!response.ok) {
            throw new Error("Failed to reset conversation history.");
        }
        return await response.json();
    }

    /**
     * Probe backend service health from GET /api/health.
     * Reports SQLite and API connectivity without triggering external LLM calls.
     */
    async function checkHealth() {
        try {
            const response = await fetch("/api/health");
            if (!response.ok) {
                return { status: "unhealthy", httpStatus: response.status };
            }
            return await response.json();
        } catch (err) {
            return { status: "offline", error: err.message };
        }
    }

    return {
        generateUUID,
        getSessionId,
        rotateSessionId,
        sendChatMessage,
        fetchMetrics,
        resetConversation,
        checkHealth,
    };
})();
