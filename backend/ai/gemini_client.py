"""Official Google Gen AI client wrapper with secure lifecycle and error classification."""

import asyncio
import os
import random
import re
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load local environment configuration if present
load_dotenv()

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

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
)


class GeminiClient:
    """Manages the lifecycle and execution of requests to the Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
        call_hook: Optional[Any] = None,
    ):
        """Initialize the Gemini client with environment-backed configuration.
        
        Args:
            api_key: Optional Gemini API key (defaults to GEMINI_API_KEY env var).
            model: Optional model identifier (defaults to GEMINI_MODEL env var or 'gemini-3.8-flash').
            timeout: Request timeout in seconds (defaults to GEMINI_TIMEOUT_SECONDS or 30).
            temperature: Sampling temperature (defaults to GEMINI_TEMPERATURE or 0.2).
            max_output_tokens: Maximum tokens in response (defaults to GEMINI_MAX_OUTPUT_TOKENS or 400).
            max_retries: Maximum bounded retry attempts (defaults to GEMINI_MAX_RETRIES or 2).
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        
        timeout_env = os.getenv("GEMINI_TIMEOUT_SECONDS")
        self.timeout = float(timeout if timeout is not None else (timeout_env if timeout_env else 30.0))
        
        temp_env = os.getenv("GEMINI_TEMPERATURE")
        self.temperature = float(temperature if temperature is not None else (temp_env if temp_env else 0.2))
        
        tokens_env = os.getenv("GEMINI_MAX_OUTPUT_TOKENS")
        self.max_output_tokens = int(max_output_tokens if max_output_tokens is not None else (tokens_env if tokens_env else 400))
        
        retries_env = os.getenv("GEMINI_MAX_RETRIES")
        self.max_retries = int(max_retries if max_retries is not None else (retries_env if retries_env else 2))

        self.call_hook = call_hook
        self._client: Optional[genai.Client] = None

    def set_call_hook(self, hook: Any) -> None:
        """Register a callback invoked immediately before each outbound Gemini API request attempt."""
        self.call_hook = hook

    def _ensure_client(self) -> genai.Client:
        """Lazily initialize and validate the official Gen AI client.
        
        Raises:
            MissingAPIKeyError: If GEMINI_API_KEY is not provided.
        """
        if not self.api_key or not self.api_key.strip():
            raise MissingAPIKeyError("GEMINI_API_KEY is not configured in the environment.")

        if self._client is None:
            # Initialize official Google Gen AI client
            self._client = genai.Client(api_key=self.api_key)
        
        return self._client

    async def close(self) -> None:
        """Perform explicit client cleanup during application shutdown."""
        if self._client is not None:
            # google-genai Client delegates aio session cleanup
            try:
                if hasattr(self._client, "aio") and hasattr(self._client.aio, "close"):
                    await self._client.aio.close()
            except Exception:
                pass
            self._client = None

    def _classify_error(self, err: Exception) -> GeminiError:
        """Map raw Gen AI SDK or transport exceptions into structured application exceptions."""
        if isinstance(err, GeminiError):
            return err

        if isinstance(err, asyncio.TimeoutError):
            return TimeoutError(f"Request exceeded timeout of {self.timeout}s.")

        # Inspect official Google Gen AI API errors
        if isinstance(err, genai_errors.APIError):
            code = getattr(err, "code", 0)
            msg = getattr(err, "message", str(err))

            if code in (401, 403):
                return AuthenticationError(f"Authentication failed (code {code}): {msg}")
            
            if code == 404:
                return ModelNotFoundError(self.model, f"Model not found (code 404): {msg}")

            if code == 429:
                # Differentiate transient rate limit from hard quota exhaustion
                if "quota" in msg.lower() or "resource_exhausted" in msg.lower():
                    return QuotaExceededError(f"Resource quota exhausted: {msg}")
                # Check for Retry-After hint
                retry_after: Optional[float] = None
                match = re.search(r"retry[- ]after[:\s]+(\d+)", msg, re.IGNORECASE)
                if match:
                    retry_after = float(match.group(1))
                return RateLimitError(f"Rate limit exceeded: {msg}", retry_after=retry_after)

            if code >= 500:
                return NetworkError(f"Gemini server error (code {code}): {msg}")

        # Check for generic network or transport connection errors
        err_str = str(err).lower()
        if any(term in err_str for term in ["connect", "socket", "dns", "broken pipe", "connection refused"]):
            return NetworkError(f"Network connectivity error: {err}")

        return GeminiError(f"Unhandled Gemini API error: {err}")

    async def generate_content_async(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: Optional[Any] = None,
    ) -> str:
        """Execute an asynchronous generation request with bounded retry and backoff.

        Args:
            prompt: Formatted user prompt with authoritative evidence.
            system_instruction: Grounded system instructions.
            response_schema: Optional Pydantic model for structured JSON schema.

        Returns:
            str: The raw generated text or JSON string from Gemini.

        Raises:
            MissingAPIKeyError: If API key is missing.
            AuthenticationError: On 401/403.
            ModelNotFoundError: On 404.
            RateLimitError: On unrecovered 429.
            QuotaExceededError: On quota exhaustion.
            NetworkError: On transport failure.
            TimeoutError: If all retries time out.
            InvalidResponseError: If response is empty or blocked.
        """
        client = self._ensure_client()

        config_kwargs: Dict[str, Any] = {
            "system_instruction": system_instruction,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }

        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Instrument outbound attempt counter immediately before dispatch
                if self.call_hook:
                    if asyncio.iscoroutinefunction(self.call_hook):
                        await self.call_hook()
                    else:
                        self.call_hook()

                # Wrap generation inside timeout
                async with asyncio.timeout(self.timeout):
                    response = await client.aio.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    )

                if response is None or not response.text or not response.text.strip():
                    raise InvalidResponseError("Gemini returned an empty response.")

                return response.text.strip()

            except Exception as e:
                classified = self._classify_error(e)
                last_error = classified

                # Do not retry on permanent errors
                if isinstance(classified, (AuthenticationError, ModelNotFoundError, QuotaExceededError, MissingAPIKeyError)):
                    raise classified

                # If attempts exhausted, break to raise
                if attempt >= self.max_retries:
                    break

                # Calculate exponential backoff with jitter
                delay = (2.0 ** attempt) + random.uniform(0.1, 0.5)
                if isinstance(classified, RateLimitError) and classified.retry_after:
                    delay = max(delay, classified.retry_after)

                await asyncio.sleep(delay)

        if last_error:
            raise last_error

        raise GeminiError("Generation failed after maximum retries.")
