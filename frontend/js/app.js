/**
 * Application controller orchestrating chat, telemetry, and input interactions.
 */

document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const sendButton = document.getElementById("send-button");
    const charCounter = document.getElementById("char-counter");
    const resetButton = document.getElementById("reset-button");
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");

    let isSubmitting = false;

    // Initialize session ID
    let currentSessionId = ApiClient.getSessionId();

    // Initial metrics fetch
    MetricsController.refreshMetrics();

    /**
     * Update backend connection health status.
     * Note: Accurately reports backend/SQLite health; does not imply Gemini is online.
     */
    async function updateBackendStatus() {
        if (!statusDot || !statusText) return;
        try {
            const health = await ApiClient.checkHealth();
            if (health && health.status === "healthy") {
                statusDot.className = "status-dot healthy";
                statusText.textContent = "Backend Connected";
                statusText.title = "FastAPI application and SQLite WAL operational";
            } else {
                statusDot.className = "status-dot degraded";
                statusText.textContent = "Backend Degraded";
                statusText.title = "Database or application issue reported";
            }
        } catch (err) {
            statusDot.className = "status-dot offline";
            statusText.textContent = "Backend Offline";
            statusText.title = "Cannot reach FastAPI backend";
        }
    }

    // Check health on load and every 30 seconds
    updateBackendStatus();
    setInterval(updateBackendStatus, 30000);

    /**
     * Auto-resize textarea and update character counter.
     */
    function handleInputResize() {
        userInput.style.height = "auto";
        userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
        const len = userInput.value.length;
        charCounter.textContent = `${len} / 1000`;
    }

    userInput.addEventListener("input", handleInputResize);

    /**
     * Handle keyboard shortcuts: Enter to send, Shift+Enter for newline.
     */
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitQuestion();
        }
    });

    /**
     * Handle form submission.
     */
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        submitQuestion();
    });

    /**
     * Core submission logic with idempotency and double-click protection.
     */
    async function submitQuestion(questionText = null) {
        const text = (questionText || userInput.value).trim();
        if (!text || isSubmitting) return;

        isSubmitting = true;
        sendButton.disabled = true;
        userInput.disabled = true;
        ChatController.hideError();

        // If submitted from input box, clear it
        if (!questionText) {
            userInput.value = "";
            handleInputResize();
        }

        // Render user question bubble
        ChatController.renderUserMessage(text);
        ChatController.showTyping();

        // Generate per-request UUID idempotency key
        const idempotencyKey = ApiClient.generateUUID();

        try {
            const data = await ApiClient.sendChatMessage(currentSessionId, text, idempotencyKey);
            ChatController.hideTyping();

            // Render assistant answer bubble
            ChatController.renderAssistantMessage(
                data.answer,
                data.sources || [],
                data.is_supported !== false,
                data.served_from_cache === true
            );

            // Update live metrics from response
            if (data.metrics) {
                MetricsController.updateMetrics(data.metrics);
            }
        } catch (err) {
            ChatController.hideTyping();
            ChatController.showError(err.message || "An unexpected error occurred. Please try again.");
        } finally {
            isSubmitting = false;
            sendButton.disabled = false;
            userInput.disabled = false;
            userInput.focus();
        }
    }

    /**
     * Bind click handlers to starter suggestion chips.
     */
    document.querySelectorAll(".suggestion-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const question = chip.textContent.trim();
            submitQuestion(question);
        });
    });

    /**
     * Reset conversation session history.
     */
    resetButton.addEventListener("click", async () => {
        if (isSubmitting) return;

        const confirmReset = window.confirm("Reset conversation? This will clear the chat history for this session.");
        if (!confirmReset) return;

        try {
            await ApiClient.resetConversation(currentSessionId);
            currentSessionId = ApiClient.rotateSessionId();
            ChatController.resetMessagesView();
        } catch (err) {
            ChatController.showError("Failed to reset conversation: " + err.message);
        }
    });

    // Focus input on initial page load
    userInput.focus();
});
