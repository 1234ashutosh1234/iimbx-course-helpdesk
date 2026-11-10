"""Unit tests for error classification and user-friendly messaging."""

from backend.ai.exceptions import (
    GeminiError,
    MissingAPIKeyError,
    AuthenticationError,
    ModelNotFoundError,
    RateLimitError,
    QuotaExceededError,
    NetworkError,
    TimeoutError,
    InvalidResponseError,
    AnswerValidationError,
)


def test_missing_api_key_error_message():
    """Verify clean message for missing key without secret exposure."""
    err = MissingAPIKeyError()
    assert "not configured" in err.message
    assert "configuration is incomplete" in err.user_friendly_message
    assert "secret" not in err.user_friendly_message.lower()


def test_authentication_error_message():
    """Verify friendly message on 401/403."""
    err = AuthenticationError("Invalid key")
    assert "Authentication with the AI service failed" in err.user_friendly_message


def test_rate_limit_and_quota_error_messages():
    """Verify friendly message on 429 rate limit vs quota exhaustion."""
    rate_err = RateLimitError("Rate limit hit")
    assert "temporarily busy" in rate_err.user_friendly_message

    quota_err = QuotaExceededError("Quota exhausted")
    assert "reached its request limit" in quota_err.user_friendly_message


def test_timeout_and_network_error_messages():
    """Verify friendly message on network and timeout errors."""
    timeout_err = TimeoutError("Deadline exceeded")
    assert "took too long to respond" in timeout_err.user_friendly_message

    net_err = NetworkError("Socket closed")
    assert "Could not connect" in net_err.user_friendly_message


def test_invalid_response_and_validation_error_messages():
    """Verify friendly message on empty or invalid response."""
    inv_err = InvalidResponseError("Empty text")
    assert "returned an unreadable response" in inv_err.user_friendly_message

    val_err = AnswerValidationError("Missing 60%", topic="PASSING_CRITERIA")
    assert "Falling back to authoritative course policy" in val_err.user_friendly_message
