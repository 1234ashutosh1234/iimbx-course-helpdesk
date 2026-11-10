/**
 * Metrics controller for live system telemetry display.
 */

const MetricsController = (() => {
    const elTotalQuestions = document.getElementById("metric-total-questions");
    const elGeminiCalls = document.getElementById("metric-gemini-calls");
    const elCacheHits = document.getElementById("metric-cache-hits");

    /**
     * Update the three telemetry counters in the UI.
     * Safely updates text content without innerHTML.
     */
    function updateMetrics(metrics) {
        if (!metrics) return;

        if (elTotalQuestions && typeof metrics.total_questions === "number") {
            elTotalQuestions.textContent = metrics.total_questions.toLocaleString();
        }
        if (elGeminiCalls && typeof metrics.gemini_calls === "number") {
            elGeminiCalls.textContent = metrics.gemini_calls.toLocaleString();
        }
        if (elCacheHits && typeof metrics.cache_hits === "number") {
            elCacheHits.textContent = metrics.cache_hits.toLocaleString();
        }
    }

    /**
     * Poll / fetch live metrics from backend.
     */
    async function refreshMetrics() {
        try {
            const data = await ApiClient.fetchMetrics();
            updateMetrics(data);
        } catch (err) {
            console.warn("Could not refresh live metrics:", err.message);
        }
    }

    return {
        updateMetrics,
        refreshMetrics,
    };
})();
