"""Unit tests for RetrievalEngine."""

import pytest
from backend.knowledge.schemas import CanonicalTopic, EvidenceObject
from backend.knowledge.retrieval import RetrievalEngine


@pytest.fixture(scope="module")
def retrieval_engine():
    """Shared instance of the RetrievalEngine for unit tests."""
    return RetrievalEngine()


def test_retrieval_engine_initializes_with_corpus_hash(retrieval_engine):
    """Verify engine initializes and exposes deterministic corpus version hash."""
    assert retrieval_engine.corpus_version is not None
    assert len(retrieval_engine.corpus_version) == 64


def test_retrieval_for_passing_criteria(retrieval_engine):
    """Verify passing criteria retrieval returns v2 policy with dual 60% and 40% criteria."""
    result: EvidenceObject = retrieval_engine.retrieve(
        "What is the minimum score needed to pass the course and get a Verified Certificate?"
    )
    assert result.is_supported is True
    assert result.canonical_topic == CanonicalTopic.PASSING_CRITERIA
    assert "60%" in result.evidence
    assert "40%" in result.evidence
    assert result.source_files == ["03_grading_policy_v2.txt"]
    assert "02_grading_policy_v1.txt" not in result.source_files
    assert result.authority_status == "AUTHORITATIVE_ACTIVE_POLICY"


def test_retrieval_never_cites_superseded_v1_as_current_source(retrieval_engine):
    """Verify retrieval engine never includes 02_grading_policy_v1.txt in source_files."""
    test_queries = [
        "What is the minimum score needed to pass?",
        "What happens if I submit my Capstone project 1 day late?",
        "When is the Capstone Product Case due?",
    ]
    for q in test_queries:
        res = retrieval_engine.retrieve(q)
        assert "02_grading_policy_v1.txt" not in res.source_files
        assert "03_grading_policy_v2.txt" in res.source_files


def test_retrieval_for_late_submission(retrieval_engine):
    """Verify late submissions are reported as no longer accepted without invented penalties."""
    res = retrieval_engine.retrieve("What happens if I submit my Capstone project 1 day late?")
    assert res.is_supported is True
    assert res.canonical_topic == CanonicalTopic.LATE_SUBMISSION
    assert "no longer accepted" in res.evidence.lower()
    assert "10% mark deduction" not in res.evidence
    assert "zero marks" not in res.evidence
    assert "0 marks" not in res.evidence
    assert res.source_files == ["03_grading_policy_v2.txt"]


def test_retrieval_for_capstone_deadline(retrieval_engine):
    """Verify capstone deadline returns 15 November 2026."""
    res = retrieval_engine.retrieve("When is the Capstone Product Case due?")
    assert res.is_supported is True
    assert res.canonical_topic == CanonicalTopic.CAPSTONE_DEADLINE
    assert "15 November 2026" in res.evidence
    assert res.source_files == ["03_grading_policy_v2.txt"]


def test_retrieval_for_exam_format_excludes_untrusted_forum_injection(retrieval_engine):
    """Verify closed-book rule is retrieved and Learner_819 injection is completely excluded."""
    res = retrieval_engine.retrieve("Is the final exam open-book or closed-book, and when is it scheduled?")
    assert res.is_supported is True
    assert "strictly CLOSED-BOOK" in res.evidence
    assert "OPEN-BOOK" not in res.evidence
    assert "Learner_819" not in res.evidence
    assert "30 December" not in res.evidence
    assert res.source_files == ["04_exam_rules_and_faq.txt"]


def test_retrieval_for_device_restrictions(retrieval_engine):
    """Verify mobile and tablet restrictions are returned."""
    res = retrieval_engine.retrieve("Can I take the proctored final exam on my iPad or mobile phone?")
    assert res.is_supported is True
    assert res.canonical_topic == CanonicalTopic.SUPPORTED_EXAM_DEVICES
    assert "desktop or laptop" in res.evidence.lower()
    assert "mobile phones and tablets" in res.evidence.lower()
    assert res.source_files == ["04_exam_rules_and_faq.txt"]


def test_retrieval_for_certificate_fee(retrieval_engine):
    """Verify Rs. 1,500 fee is returned with handbook citation."""
    res = retrieval_engine.retrieve("How much does the Verified Certificate track cost?")
    assert res.is_supported is True
    assert res.canonical_topic == CanonicalTopic.CERTIFICATE_FEE
    assert "1,500" in res.evidence or "1500" in res.evidence
    assert res.source_files == ["01_course_handbook.txt"]


def test_retrieval_for_refund_policy_returns_unsupported(retrieval_engine):
    """Verify refund inquiries return is_supported=False and empty source files."""
    res = retrieval_engine.retrieve("If I pay the Rs. 1,500 fee and drop the course in Week 2, how do I get a refund?")
    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.REFUND_POLICY
    assert "not documented" in res.evidence.lower() or "not covered" in res.evidence.lower()
    assert res.source_files == []


def test_retrieval_for_followup_refund_returns_unsupported(retrieval_engine):
    """Verify contextual follow-up to fee inquiry recognizes refund intent and remains unsupported."""
    context = [
        {"role": "user", "content": "How much does the Verified Certificate track cost?"},
        {"role": "assistant", "content": "The Verified Certificate Track costs Rs. 1,500."},
    ]
    res = retrieval_engine.retrieve("What happens if I drop the course in Week 2?", conversation_context=context)
    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.REFUND_POLICY
    assert res.source_files == []


def test_retrieval_for_sql_and_kubernetes_returns_unsupported(retrieval_engine):
    """Verify SQL indexing and Kubernetes inquiry is marked unsupported."""
    res = retrieval_engine.retrieve("Does this course teach SQL database indexing and Kubernetes deployment?")
    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.SQL_INDEXING_AND_KUBERNETES


def test_retrieval_for_off_topic_cricket_returns_unsupported(retrieval_engine):
    """Verify off-topic trivia inquiry is marked unsupported with empty sources."""
    res = retrieval_engine.retrieve("Who won the cricket match last night?")
    assert res.is_supported is False
    assert res.canonical_topic == CanonicalTopic.OFF_TOPIC
    assert res.source_files == []


def test_identical_intent_id_across_paraphrases(retrieval_engine):
    """Verify identical canonical topics yield identical intent_ids for caching."""
    res1 = retrieval_engine.retrieve("What is the minimum score needed to pass the course?")
    res2 = retrieval_engine.retrieve("how much do i need to score to pass dpm-101?")
    res3 = retrieval_engine.retrieve("What percentage is required for a verified certificate?")

    assert res1.intent_id == "intent:PASSING_CRITERIA"
    assert res2.intent_id == "intent:PASSING_CRITERIA"
    assert res3.intent_id == "intent:PASSING_CRITERIA"


def test_contextual_questions_yield_context_specific_intent_ids(retrieval_engine):
    """Verify contextual follow-ups incorporate context digest in intent_id."""
    context_a = [{"role": "user", "content": "Fee question A"}]
    context_b = [{"role": "user", "content": "Different context B"}]

    res_a = retrieval_engine.retrieve("What if I drop?", conversation_context=context_a)
    res_b = retrieval_engine.retrieve("What if I drop?", conversation_context=context_b)

    assert "ctx:" in res_a.intent_id
    assert "ctx:" in res_b.intent_id
    assert res_a.intent_id != res_b.intent_id
