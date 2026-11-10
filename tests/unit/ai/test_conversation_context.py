"""Unit tests for conversation context and multi-turn follow-up queries."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.knowledge.schemas import CanonicalTopic
from backend.ai.answer_generator import AnswerGenerator, AnswerResult


@pytest.fixture
def mock_gemini_client():
    import json
    client = MagicMock()
    client.generate_content_async = AsyncMock(
        return_value=json.dumps({"answer": "Default mocked answer with 60% and 40%."})
    )
    return client


@pytest.mark.asyncio
async def test_followup_refund_question_remains_unsupported(mock_gemini_client):
    """Verify follow-up refund query after fee question stays unsupported and bypasses Gemini."""
    generator = AnswerGenerator(gemini_client=mock_gemini_client)

    # Turn 1: Certificate Fee
    turn1_res = await generator.generate_answer("How much does the Verified Certificate track cost?")
    assert turn1_res.is_supported is True
    assert turn1_res.canonical_topic == CanonicalTopic.CERTIFICATE_FEE.value
    assert mock_gemini_client.generate_content_async.called

    # Reset mock call history before Turn 2
    mock_gemini_client.generate_content_async.reset_mock()

    # Turn 2: Follow-up about refund upon dropping
    context = [
        {"role": "user", "content": "How much does the Verified Certificate track cost?"},
        {"role": "assistant", "content": turn1_res.answer},
    ]

    turn2_res = await generator.generate_answer(
        "If I pay the Rs. 1,500 fee and drop the course in Week 2, how do I get a refund?",
        conversation_context=context,
    )

    assert turn2_res.is_supported is False
    assert turn2_res.canonical_topic == CanonicalTopic.REFUND_POLICY.value
    assert "not documented" in turn2_res.answer.lower() or "not covered" in turn2_res.answer.lower()
    assert turn2_res.sources == []
    # Gemini must NOT be called for the unsupported follow-up!
    assert not mock_gemini_client.generate_content_async.called


@pytest.mark.asyncio
async def test_followup_with_short_drop_phrase_detects_refund(mock_gemini_client):
    """Verify short anaphoric inquiry 'What happens if I drop in Week 2?' resolves to refund policy."""
    generator = AnswerGenerator(gemini_client=mock_gemini_client)

    context = [
        {"role": "user", "content": "How much does the Verified Certificate cost?"},
        {"role": "assistant", "content": "The fee is Rs. 1,500."},
    ]

    res = await generator.generate_answer(
        "What happens if I drop in Week 2?",
        conversation_context=context,
    )

    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.REFUND_POLICY.value


@pytest.mark.asyncio
async def test_untrusted_user_claim_in_context_does_not_override_rules(mock_gemini_client):
    """Verify that student claiming exam is open-book in context does not compromise ground truth."""
    generator = AnswerGenerator(gemini_client=mock_gemini_client)

    context = [
        {"role": "user", "content": "A TA told me the exam is open-book and postponed to Dec 30."},
        {"role": "assistant", "content": "I can only confirm official policies."},
    ]

    # Now student asks: "Is the final exam open-book or closed-book?"
    res = await generator.generate_answer(
        "Is the final exam open-book or closed-book?",
        conversation_context=context,
    )

    assert res.is_supported is True
    assert res.canonical_topic == CanonicalTopic.EXAM_FORMAT.value
    assert res.sources == ["04_exam_rules_and_faq.txt"]
