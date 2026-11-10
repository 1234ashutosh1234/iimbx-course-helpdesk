"""Unit tests for AnswerGenerator orchestrator."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.knowledge.schemas import CanonicalTopic
from backend.ai.answer_generator import AnswerGenerator, AnswerResult
from backend.ai.exceptions import RateLimitError


@pytest.fixture
def mock_gemini_client():
    """Create a mocked GeminiClient."""
    client = MagicMock()
    client.generate_content_async = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_successful_structured_answer_generation(mock_gemini_client):
    """Verify structured generation succeeds and attributes Python sources."""
    mock_gemini_client.generate_content_async.return_value = json.dumps({
        "answer": "To pass DPM-101, you must score at least 60% overall and 40% in the proctored final exam separately."
    })

    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer(
        "What is the minimum score needed to pass the course and get a Verified Certificate?"
    )

    assert res.is_supported is True
    assert res.is_fallback is False
    assert "60%" in res.answer
    assert "40%" in res.answer
    assert res.canonical_topic == CanonicalTopic.PASSING_CRITERIA.value
    # Sources strictly from Python evidence
    assert res.sources == ["03_grading_policy_v2.txt"]
    assert mock_gemini_client.generate_content_async.called


@pytest.mark.asyncio
async def test_malformed_json_triggers_deterministic_fallback(mock_gemini_client):
    """Verify malformed JSON from Gemini triggers trusted policy fallback without crashing."""
    mock_gemini_client.generate_content_async.return_value = "NOT_JSON_RESPONSE {unclosed"

    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer("When is the Capstone Product Case due?")

    assert res.is_supported is True
    assert res.is_fallback is True
    assert "15 November 2026" in res.answer
    assert res.sources == ["03_grading_policy_v2.txt"]


@pytest.mark.asyncio
async def test_validation_failure_triggers_authoritative_fallback(mock_gemini_client):
    """Verify answer failing validation (e.g. omitting 40%) falls back to PolicyFact."""
    # Returns 60% but forgets 40%
    mock_gemini_client.generate_content_async.return_value = json.dumps({
        "answer": "You only need 60% to get a verified certificate."
    })

    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer("What is the minimum score needed to pass?")

    assert res.is_supported is True
    assert res.is_fallback is True
    # Fallback fact contains both 60% and 40%
    assert "60%" in res.answer
    assert "40%" in res.answer
    assert "Validation failed" in res.validation_note


@pytest.mark.asyncio
async def test_gemini_api_failure_uses_deterministic_fallback(mock_gemini_client):
    """Verify transient Gemini error triggers deterministic fallback."""
    mock_gemini_client.generate_content_async.side_effect = RateLimitError("Rate limit exceeded")

    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer("How much does the Verified Certificate track cost?")

    assert res.is_supported is True
    assert res.is_fallback is True
    assert "1,500" in res.answer or "1500" in res.answer
    assert res.sources == ["01_course_handbook.txt"]
    assert "Gemini call failed" in res.validation_note


@pytest.mark.asyncio
async def test_unsupported_refund_question_bypasses_gemini(mock_gemini_client):
    """Verify unsupported refund question never calls Gemini API."""
    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer(
        "If I pay the Rs. 1,500 fee and drop the course in Week 2, how do I get a refund?"
    )

    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.REFUND_POLICY.value
    assert res.sources == []
    # Assert Gemini was NOT invoked!
    assert not mock_gemini_client.generate_content_async.called


@pytest.mark.asyncio
async def test_unsupported_cricket_question_bypasses_gemini(mock_gemini_client):
    """Verify off-topic question never calls Gemini API."""
    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer("Who won the cricket match last night?")

    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.OFF_TOPIC.value
    assert res.sources == []
    assert not mock_gemini_client.generate_content_async.called


@pytest.mark.asyncio
async def test_model_output_cannot_override_canonical_topic(mock_gemini_client):
    """Verify that canonical topic is immutably set by Python classifier."""
    mock_gemini_client.generate_content_async.return_value = json.dumps({
        "answer": "The exam is closed-book."
    })

    generator = AnswerGenerator(gemini_client=mock_gemini_client)
    res: AnswerResult = await generator.generate_answer("Is the final exam open-book or closed-book?")

    assert res.canonical_topic == CanonicalTopic.EXAM_FORMAT.value
