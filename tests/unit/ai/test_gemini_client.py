"""Unit tests for GeminiClient with mocked Google Gen AI SDK."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from google.genai import errors as genai_errors
from backend.ai.gemini_client import GeminiClient
from backend.ai.exceptions import (
    MissingAPIKeyError,
    AuthenticationError,
    ModelNotFoundError,
    RateLimitError,
    QuotaExceededError,
    TimeoutError,
    NetworkError,
    InvalidResponseError,
)


@pytest.fixture
def mock_genai_client():
    """Mock the official genai.Client instance."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock()
    client.aio.close = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_successful_gemini_response(mock_genai_client):
    """Verify successful response generation from Gemini client."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({"answer": "You need 60% overall and 40% in final exam."})
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    client = GeminiClient(api_key="test_key", model="gemini-3.8-flash")
    client._client = mock_genai_client

    result = await client.generate_content_async(
        prompt="What is the passing score?",
        system_instruction="Follow course rules."
    )

    assert result == mock_response.text.strip()
    assert mock_genai_client.aio.models.generate_content.called


@pytest.mark.asyncio
async def test_missing_api_key_raises_error():
    """Verify MissingAPIKeyError is raised when api_key is None or empty."""
    with patch.dict("os.environ", {}, clear=True):
        client = GeminiClient(api_key=None)
        with pytest.raises(MissingAPIKeyError):
            await client.generate_content_async("query", "instruction")


@pytest.mark.asyncio
async def test_authentication_error_on_401_403(mock_genai_client):
    """Verify AuthenticationError is raised on 401/403 and never retried."""
    error = genai_errors.ClientError(code=401, response_json={"error": {"message": "Invalid API Key"}})
    mock_genai_client.aio.models.generate_content.side_effect = error

    client = GeminiClient(api_key="invalid_key", max_retries=2)
    client._client = mock_genai_client

    with pytest.raises(AuthenticationError):
        await client.generate_content_async("query", "instruction")

    # Ensure no pointless retries on permanent authentication failure
    assert mock_genai_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_model_not_found_on_404(mock_genai_client):
    """Verify ModelNotFoundError is raised on 404."""
    error = genai_errors.ClientError(code=404, response_json={"error": {"message": "Model not found"}})
    mock_genai_client.aio.models.generate_content.side_effect = error

    client = GeminiClient(api_key="test_key", model="unknown-model-xyz")
    client._client = mock_genai_client

    with pytest.raises(ModelNotFoundError):
        await client.generate_content_async("query", "instruction")

    assert mock_genai_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_rate_limit_error_429(mock_genai_client):
    """Verify RateLimitError is raised when rate limits persist through retries."""
    error = genai_errors.ClientError(code=429, response_json={"error": {"message": "Rate limit exceeded. Please retry after 1s."}})
    mock_genai_client.aio.models.generate_content.side_effect = error

    client = GeminiClient(api_key="test_key", max_retries=1)
    client._client = mock_genai_client

    with pytest.raises(RateLimitError):
        await client.generate_content_async("query", "instruction")

    assert mock_genai_client.aio.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_quota_exceeded_error_429(mock_genai_client):
    """Verify QuotaExceededError is raised for resource quota exhaustion."""
    error = genai_errors.ClientError(code=429, response_json={"error": {"message": "RESOURCE_EXHAUSTED: quota exceeded"}})
    mock_genai_client.aio.models.generate_content.side_effect = error

    client = GeminiClient(api_key="test_key", max_retries=2)
    client._client = mock_genai_client

    with pytest.raises(QuotaExceededError):
        await client.generate_content_async("query", "instruction")

    # Does not retry on hard quota exhaustion
    assert mock_genai_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_timeout_error(mock_genai_client):
    """Verify TimeoutError is raised when request exceeds configured timeout."""
    async def slow_call(*args, **kwargs):
        await asyncio.sleep(0.5)
        return MagicMock()

    mock_genai_client.aio.models.generate_content.side_effect = slow_call

    client = GeminiClient(api_key="test_key", timeout=0.05, max_retries=0)
    client._client = mock_genai_client

    with pytest.raises(TimeoutError):
        await client.generate_content_async("query", "instruction")


@pytest.mark.asyncio
async def test_empty_response_raises_invalid_response(mock_genai_client):
    """Verify InvalidResponseError is raised when model returns empty text."""
    empty_response = MagicMock()
    empty_response.text = ""
    mock_genai_client.aio.models.generate_content.return_value = empty_response

    client = GeminiClient(api_key="test_key", max_retries=0)
    client._client = mock_genai_client

    with pytest.raises(InvalidResponseError):
        await client.generate_content_async("query", "instruction")


@pytest.mark.asyncio
async def test_client_close_cleanup(mock_genai_client):
    """Verify close() cleanly triggers aio session shutdown."""
    client = GeminiClient(api_key="test_key")
    client._client = mock_genai_client

    await client.close()
    assert client._client is None
    assert mock_genai_client.aio.close.called
