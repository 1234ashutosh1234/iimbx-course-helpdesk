"""Gemini AI integration package for IIMBx Course Helpdesk."""

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
from backend.ai.prompts import SYSTEM_INSTRUCTION, build_generation_prompt
from backend.ai.response_validator import ResponseValidator
from backend.ai.gemini_client import GeminiClient
from backend.ai.answer_generator import AnswerGenerator, GeneratedAnswer, AnswerResult

__all__ = [
    "GeminiError",
    "MissingAPIKeyError",
    "AuthenticationError",
    "ModelNotFoundError",
    "RateLimitError",
    "QuotaExceededError",
    "NetworkError",
    "TimeoutError",
    "InvalidResponseError",
    "AnswerValidationError",
    "SYSTEM_INSTRUCTION",
    "build_generation_prompt",
    "ResponseValidator",
    "GeminiClient",
    "AnswerGenerator",
    "GeneratedAnswer",
    "AnswerResult",
]
