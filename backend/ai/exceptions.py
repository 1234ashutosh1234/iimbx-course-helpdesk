"""Custom exception hierarchy for Gemini AI integration."""

from typing import Optional


class GeminiError(Exception):
    """Base exception for all Gemini AI related operations."""

    def __init__(self, message: str, user_friendly_message: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.user_friendly_message = (
            user_friendly_message or "Our AI service is temporarily unavailable. Please try again later."
        )


class MissingAPIKeyError(GeminiError):
    """Raised when GEMINI_API_KEY is missing or empty."""

    def __init__(self, message: str = "GEMINI_API_KEY environment variable is not configured."):
        super().__init__(
            message=message,
            user_friendly_message="AI service configuration is incomplete. Please contact the administrator."
        )


class AuthenticationError(GeminiError):
    """Raised when the API key is invalid or lacks permissions (HTTP 401 / 403)."""

    def __init__(self, message: str = "Gemini API authentication failed. Check GEMINI_API_KEY."):
        super().__init__(
            message=message,
            user_friendly_message="Authentication with the AI service failed. Please contact the administrator."
        )


class ModelNotFoundError(GeminiError):
    """Raised when the requested Gemini model is not found or not accessible (HTTP 404)."""

    def __init__(self, model_name: str, message: Optional[str] = None):
        msg = message or f"Gemini model '{model_name}' was not found or is not accessible with this API key."
        super().__init__(
            message=msg,
            user_friendly_message="The requested AI model is currently unavailable. Please try again later."
        )
        self.model_name = model_name


class RateLimitError(GeminiError):
    """Raised when rate limits are exceeded (HTTP 429)."""

    def __init__(self, message: str = "Gemini API rate limit exceeded.", retry_after: Optional[float] = None):
        super().__init__(
            message=message,
            user_friendly_message="Sorry, our AI service is temporarily busy. Please try again shortly."
        )
        self.retry_after = retry_after


class QuotaExceededError(GeminiError):
    """Raised when API quota has been completely exhausted."""

    def __init__(self, message: str = "Gemini API resource quota exhausted."):
        super().__init__(
            message=message,
            user_friendly_message="Our AI service has reached its request limit for today. Please try again later."
        )


class NetworkError(GeminiError):
    """Raised when a network connectivity failure occurs."""

    def __init__(self, message: str = "Network error connecting to Gemini API."):
        super().__init__(
            message=message,
            user_friendly_message="Could not connect to the AI service. Please check your internet connection."
        )


class TimeoutError(GeminiError):
    """Raised when a request to Gemini times out."""

    def __init__(self, message: str = "Request to Gemini API timed out."):
        super().__init__(
            message=message,
            user_friendly_message="The AI service took too long to respond. Please try again shortly."
        )


class InvalidResponseError(GeminiError):
    """Raised when Gemini returns an empty, blocked, or unparseable response."""

    def __init__(self, message: str = "Gemini returned an invalid or unparseable response."):
        super().__init__(
            message=message,
            user_friendly_message="The AI service returned an unreadable response. Please try again."
        )


class AnswerValidationError(GeminiError):
    """Raised when a generated answer fails mandatory factual anchor checks."""

    def __init__(self, message: str, topic: str):
        super().__init__(
            message=f"Answer validation failed for topic '{topic}': {message}",
            user_friendly_message="Factual validation failed. Falling back to authoritative course policy."
        )
        self.topic = topic
