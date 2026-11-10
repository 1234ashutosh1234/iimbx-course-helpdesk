"""Tests for Multi-Intent Question Handling and Document-Grounded Wording.

Covers:
1. Date-only question.
2. Format-only question.
3. Combined date and format question.
4. Different ordering of the two intents.
5. Combined question with paraphrased wording.
6. Correct source attribution.
7. Both required facts present in generated/deterministic response.
8. Grounded phrasing and handbook attribution for SQL/Kubernetes unsupported query.
9. Cache sharing across multi-intent paraphrases and inverted ordering.
"""

import pytest
from unittest.mock import AsyncMock

from backend.knowledge.schemas import CanonicalTopic, EvidenceObject
from backend.knowledge.retrieval import RetrievalEngine
from backend.knowledge.query_classifier import QueryClassifier
from backend.knowledge.policy_resolver import PolicyResolver
from backend.ai.response_validator import ResponseValidator
from backend.ai.answer_generator import AnswerGenerator
from backend.services.chat_service import ChatService
from backend.services.cache_service import CacheService
from backend.services.metrics_service import MetricsService
from backend.services.idempotency import IdempotencyService
from backend.services.request_coordinator import RequestCoordinator
from backend.database.connection import DatabaseManager


@pytest.fixture
def retrieval_engine():
    return RetrievalEngine()


@pytest.fixture
async def chat_service(tmp_path):
    db_file = str(tmp_path / "test_multi_intent.db")
    db_manager = DatabaseManager(db_path=db_file)
    await db_manager.initialize()

    retrieval = RetrievalEngine()
    mock_gemini = AsyncMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.set_call_hook = lambda hook: None

    cache_svc = CacheService(db_manager=db_manager)
    metrics_svc = MetricsService(db_manager=db_manager)
    idempotency_svc = IdempotencyService(db_manager=db_manager)
    coordinator = RequestCoordinator(db_manager=db_manager)
    answer_gen = AnswerGenerator(retrieval_engine=retrieval, gemini_client=mock_gemini)

    return ChatService(
        db_manager=db_manager,
        retrieval_engine=retrieval,
        gemini_client=mock_gemini,
        answer_generator=answer_gen,
        cache_service=cache_svc,
        metrics_service=metrics_svc,
        idempotency_service=idempotency_svc,
        request_coordinator=coordinator,
    )


# ---------------------------------------------------------------------------
# Test 1: Date-Only Question
# ---------------------------------------------------------------------------
def test_date_only_question(retrieval_engine):
    """Test 1: Single-intent question for exam date returns only date fact."""
    q = "What is the final exam date?"
    res = retrieval_engine.retrieve(q)
    assert res.is_supported is True
    assert CanonicalTopic.FINAL_EXAM_DATE in res.canonical_topics
    assert CanonicalTopic.EXAM_FORMAT not in res.canonical_topics
    assert "20 November 2026" in res.evidence
    assert res.source_files == ["04_exam_rules_and_faq.txt"]
    assert res.intent_id == "intent:FINAL_EXAM_DATE"


# ---------------------------------------------------------------------------
# Test 2: Format-Only Question
# ---------------------------------------------------------------------------
def test_format_only_question(retrieval_engine):
    """Test 2: Single-intent question for exam format returns only format fact."""
    q = "Is the final exam open book or closed book?"
    res = retrieval_engine.retrieve(q)
    assert res.is_supported is True
    assert CanonicalTopic.EXAM_FORMAT in res.canonical_topics
    assert CanonicalTopic.FINAL_EXAM_DATE not in res.canonical_topics
    assert "CLOSED-BOOK" in res.evidence or "closed-book" in res.evidence.lower()
    assert res.source_files == ["04_exam_rules_and_faq.txt"]
    assert res.intent_id == "intent:EXAM_FORMAT"


# ---------------------------------------------------------------------------
# Test 3: Combined Date and Format Question
# ---------------------------------------------------------------------------
def test_combined_date_and_format_question(retrieval_engine):
    """Test 3: Combined question retrieves both FINAL_EXAM_DATE and EXAM_FORMAT."""
    q = "What is the final exam date, and is it open-book or closed-book?"
    res = retrieval_engine.retrieve(q)
    assert res.is_supported is True
    assert set(res.canonical_topics) == {
        CanonicalTopic.FINAL_EXAM_DATE,
        CanonicalTopic.EXAM_FORMAT,
    }
    assert res.source_files == ["04_exam_rules_and_faq.txt"]
    assert "20 November 2026" in res.evidence
    assert "closed-book" in res.evidence.lower()


# ---------------------------------------------------------------------------
# Test 4: Different Ordering of the Two Intents
# ---------------------------------------------------------------------------
def test_different_ordering_of_intents(retrieval_engine):
    """Test 4: Different ordering produces consistent topics and identical intent_id."""
    q_date_first = "What is the final exam date, and is it open-book or closed-book?"
    q_format_first = "Is the final exam open-book or closed-book, and when is it scheduled?"

    res_a = retrieval_engine.retrieve(q_date_first)
    res_b = retrieval_engine.retrieve(q_format_first)

    assert set(res_a.canonical_topics) == {
        CanonicalTopic.FINAL_EXAM_DATE,
        CanonicalTopic.EXAM_FORMAT,
    }
    assert set(res_b.canonical_topics) == {
        CanonicalTopic.FINAL_EXAM_DATE,
        CanonicalTopic.EXAM_FORMAT,
    }

    # Canonical sorting guarantees shared intent_id across different orderings
    assert res_a.intent_id == "intent:EXAM_FORMAT+FINAL_EXAM_DATE"
    assert res_b.intent_id == "intent:EXAM_FORMAT+FINAL_EXAM_DATE"
    assert res_a.intent_id == res_b.intent_id


# ---------------------------------------------------------------------------
# Test 5: Combined Question with Paraphrased Wording
# ---------------------------------------------------------------------------
def test_combined_question_paraphrased_wording(retrieval_engine):
    """Test 5: Paraphrased queries map to the same multi-intent canonical pair."""
    paraphrases = [
        "What is the final exam date, and is it open-book or closed-book?",
        "When is the final exam and is it open book?",
        "When do we have the final exam and can we use notes or is it closed book?",
        "What is the exam date and format?",
    ]

    for p in paraphrases:
        res = retrieval_engine.retrieve(p)
        assert CanonicalTopic.FINAL_EXAM_DATE in res.canonical_topics, f"Failed for '{p}'"
        assert CanonicalTopic.EXAM_FORMAT in res.canonical_topics, f"Failed for '{p}'"
        assert res.intent_id == "intent:EXAM_FORMAT+FINAL_EXAM_DATE"


# ---------------------------------------------------------------------------
# Test 6: Correct Source Attribution
# ---------------------------------------------------------------------------
def test_correct_source_attribution(retrieval_engine):
    """Test 6: Validates source attribution excludes superseded files and duplicates."""
    q = "What is the final exam date, and is it open-book or closed-book?"
    res = retrieval_engine.retrieve(q)
    assert res.source_files == ["04_exam_rules_and_faq.txt"]
    assert "02_grading_policy_v1.txt" not in res.source_files


# ---------------------------------------------------------------------------
# Test 7: Both Required Facts Present in the Response
# ---------------------------------------------------------------------------
def test_both_required_facts_present(retrieval_engine):
    """Test 7: Response contains both date/slots and closed-book policy details."""
    fact = PolicyResolver.get_multi_topic_fact(
        [CanonicalTopic.FINAL_EXAM_DATE, CanonicalTopic.EXAM_FORMAT]
    )
    expected_answer = (
        "The Proctored Final Exam is scheduled for 20 November 2026, "
        "with appointment slots available between 10:00 AM and 8:00 PM IST. "
        "The examination is strictly CLOSED-BOOK. "
        "External websites, search engines, course notes and AI tools are not permitted."
    )

    assert "20 November 2026" in fact.summary
    assert "10:00 AM and 8:00 PM IST" in fact.summary
    assert "closed-book" in fact.summary.lower()
    assert "course notes and ai tools are not permitted" in fact.summary.lower()

    # Verify ResponseValidator validates the multi-topic response
    is_valid, reason = ResponseValidator.validate_topics(
        [CanonicalTopic.FINAL_EXAM_DATE, CanonicalTopic.EXAM_FORMAT],
        fact.summary
    )
    assert is_valid is True, f"Validation failed: {reason}"


# ---------------------------------------------------------------------------
# Test 8: Issue 2 — Grounded Wording for SQL & Kubernetes
# ---------------------------------------------------------------------------
def test_sql_and_kubernetes_grounded_wording(retrieval_engine):
    """Test 8: Verify exact required non-definitive wording and handbook source."""
    q = "Does this course teach SQL database indexing and Kubernetes deployment?"
    res = retrieval_engine.retrieve(q)

    expected_wording = (
        "The supplied DPM-101 course documents describe user research, product roadmapping, "
        "metrics, and AI feature design. They do not mention SQL database indexing or "
        "Kubernetes deployment."
    )

    assert res.is_supported is False
    assert res.evidence == expected_wording
    assert res.source_files == ["01_course_handbook.txt"]
    assert "not part of the dpm-101 curriculum" not in res.evidence.lower()


# ---------------------------------------------------------------------------
# Test 9: End-to-End ChatService Multi-Intent and Cache Replay
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chatservice_multi_intent_cache_sharing(chat_service):
    """Test 9: ChatService handles multi-intent query, caches it, and reuses on inverted ordering."""
    # 1. First inquiry: Date first, format second
    resp1 = await chat_service.process_question(
        question="What is the final exam date, and is it open-book or closed-book?",
        session_id="session-multi-1",
        idempotency_key="idemp-multi-1",
    )
    assert resp1.is_supported is True
    assert resp1.cache_hit is False
    assert "20 November 2026" in resp1.answer
    assert "closed-book" in resp1.answer.lower()
    assert resp1.sources == ["04_exam_rules_and_faq.txt"]
    assert resp1.canonical_topic == "EXAM_FORMAT+FINAL_EXAM_DATE"

    # 2. Second inquiry: Format first, date second (should be a CACHE HIT)
    resp2 = await chat_service.process_question(
        question="Is the final exam open-book or closed-book, and when is it scheduled?",
        session_id="session-multi-2",
        idempotency_key="idemp-multi-2",
    )
    assert resp2.is_supported is True
    assert resp2.cache_hit is True
    assert "20 November 2026" in resp2.answer
    assert "closed-book" in resp2.answer.lower()
    assert resp2.canonical_topic == "EXAM_FORMAT+FINAL_EXAM_DATE"


# ---------------------------------------------------------------------------
# Test 10: End-to-End ChatService SQL & Kubernetes Grounded Response
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chatservice_sql_and_kubernetes_grounded_response(chat_service):
    """Test 10: ChatService returns exact grounded wording with zero Gemini calls."""
    resp = await chat_service.process_question(
        question="Does this course teach SQL database indexing and Kubernetes deployment?",
        session_id="session-sql-1",
        idempotency_key="idemp-sql-1",
    )
    expected_wording = (
        "The supplied DPM-101 course documents describe user research, product roadmapping, "
        "metrics, and AI feature design. They do not mention SQL database indexing or "
        "Kubernetes deployment."
    )
    assert resp.is_supported is False
    assert resp.answer == expected_wording
    assert resp.sources == ["01_course_handbook.txt"]
    assert resp.cache_hit is False
    assert resp.metrics["gemini_calls"] == 0
