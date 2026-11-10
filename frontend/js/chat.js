/**
 * Chat controller managing DOM rendering, message bubbles, source attribution, and security.
 */

const ChatController = (() => {
    const chatMessagesEl = document.getElementById("chat-messages");
    const typingIndicatorEl = document.getElementById("typing-indicator");
    const errorBannerEl = document.getElementById("error-banner");

    /**
     * Scroll the chat message container to the bottom.
     */
    function scrollToBottom() {
        if (chatMessagesEl) {
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
        }
    }

    /**
     * Render a student inquiry message (user bubble).
     * Security: Uses textContent exclusively to prevent XSS.
     */
    function renderUserMessage(text) {
        const row = document.createElement("div");
        row.className = "message-row user";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble user";

        const textEl = document.createElement("div");
        textEl.className = "message-text";
        textEl.textContent = text;

        bubble.appendChild(textEl);
        row.appendChild(bubble);
        chatMessagesEl.appendChild(row);
        scrollToBottom();
    }

    /**
     * Render an assistant response message.
     * Security: Uses textContent exclusively for message text and source names.
     */
    function renderAssistantMessage(answer, sources = [], isSupported = true, servedFromCache = false) {
        const row = document.createElement("div");
        row.className = "message-row assistant";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble assistant";

        const authorEl = document.createElement("div");
        authorEl.className = "message-author";
        authorEl.textContent = "DPM-101 Helpdesk Assistant";
        bubble.appendChild(authorEl);

        const textEl = document.createElement("div");
        textEl.className = "message-text";
        textEl.textContent = answer;
        bubble.appendChild(textEl);

        // Render authoritative source badges if supported
        if (isSupported && Array.isArray(sources) && sources.length > 0) {
            const footerEl = document.createElement("div");
            footerEl.className = "source-footer";

            const labelEl = document.createElement("span");
            labelEl.className = "source-label";
            labelEl.textContent = "Sources:";
            footerEl.appendChild(labelEl);

            sources.forEach((source) => {
                const tagEl = document.createElement("span");
                tagEl.className = "source-tag";
                tagEl.textContent = source;
                footerEl.appendChild(tagEl);
            });

            if (servedFromCache) {
                const cacheBadge = document.createElement("span");
                cacheBadge.className = "cache-badge";
                cacheBadge.textContent = "⚡ Cached Answer";
                footerEl.appendChild(cacheBadge);
            }

            bubble.appendChild(footerEl);
        }

        row.appendChild(bubble);
        chatMessagesEl.appendChild(row);
        scrollToBottom();
    }

    /**
     * Show animated typing / loading indicator.
     */
    function showTyping() {
        if (typingIndicatorEl) {
            typingIndicatorEl.classList.remove("hidden");
            typingIndicatorEl.removeAttribute("aria-hidden");
            scrollToBottom();
        }
    }

    /**
     * Hide animated typing / loading indicator.
     */
    function hideTyping() {
        if (typingIndicatorEl) {
            typingIndicatorEl.classList.add("hidden");
            typingIndicatorEl.setAttribute("aria-hidden", "true");
        }
    }

    /**
     * Display a friendly error notification.
     */
    function showError(message) {
        if (errorBannerEl) {
            errorBannerEl.textContent = message;
            errorBannerEl.classList.remove("hidden");
        }
    }

    /**
     * Hide error banner.
     */
    function hideError() {
        if (errorBannerEl) {
            errorBannerEl.textContent = "";
            errorBannerEl.classList.add("hidden");
        }
    }

    /**
     * Reset chat messages view back to initial welcome state.
     */
    function resetMessagesView() {
        if (!chatMessagesEl) return;
        const initialWelcome = chatMessagesEl.firstElementChild;
        chatMessagesEl.innerHTML = "";
        if (initialWelcome) {
            chatMessagesEl.appendChild(initialWelcome);
        }
        hideError();
        scrollToBottom();
    }

    return {
        renderUserMessage,
        renderAssistantMessage,
        showTyping,
        hideTyping,
        showError,
        hideError,
        resetMessagesView,
        scrollToBottom,
    };
})();
