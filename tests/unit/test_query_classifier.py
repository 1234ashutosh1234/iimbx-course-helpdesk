"""Unit tests for QueryClassifier."""

from backend.knowledge.schemas import CanonicalTopic
from backend.knowledge.query_classifier import QueryClassifier, normalize_text


def test_equivalent_passing_score_questions_map_to_passing_criteria():
    """Verify paraphrased passing score questions resolve to PASSING_CRITERIA."""
    queries = [
        "What is the minimum score needed to pass the course and get a Verified Certificate?",
        "how much do i need to score to pass dpm-101?",
        "What percentage is required for a verified certificate?",
        "What is the minimum score needed to pass?",
        "What are the passing criteria for DPM-101?",
    ]
    for q in queries:
        res = QueryClassifier.classify(q)
        assert res.canonical_topic == CanonicalTopic.PASSING_CRITERIA, f"Failed for query: '{q}'"
        assert res.is_supported is True
        assert res.confidence >= 0.90


def test_late_submission_classification():
    """Verify late submission questions classify accurately."""
    queries = [
        "What happens if I submit my Capstone project 1 day late?",
        "What happens if I submit my assignment late?",
        "Is there a grace period for late submissions?",
        "What is the late penalty for weekly quizzes?",
    ]
    for q in queries:
        res = QueryClassifier.classify(q)
        assert res.canonical_topic == CanonicalTopic.LATE_SUBMISSION, f"Failed for query: '{q}'"
        assert res.is_supported is True


def test_capstone_deadline_classification():
    """Verify capstone deadline questions classify accurately."""
    queries = [
        "When is the Capstone Product Case due?",
        "What is the capstone deadline?",
        "When is the capstone due date?",
    ]
    for q in queries:
        res = QueryClassifier.classify(q)
        assert res.canonical_topic == CanonicalTopic.CAPSTONE_DEADLINE, f"Failed for query: '{q}'"
        assert res.is_supported is True


def test_exam_format_and_schedule_classification():
    """Verify closed-book and exam schedule queries classify properly."""
    res_format = QueryClassifier.classify("Is the final exam open-book or closed-book?")
    assert res_format.canonical_topic == CanonicalTopic.EXAM_FORMAT
    assert res_format.is_supported is True

    res_date = QueryClassifier.classify("When is the final exam scheduled?")
    assert res_date.canonical_topic == CanonicalTopic.FINAL_EXAM_DATE
    assert res_date.is_supported is True


def test_exam_device_restrictions_classification():
    """Verify hardware restrictions queries classify properly."""
    res = QueryClassifier.classify("Can I take the proctored final exam on my iPad or mobile phone?")
    assert res.canonical_topic == CanonicalTopic.SUPPORTED_EXAM_DEVICES
    assert res.is_supported is True


def test_certificate_fee_classification():
    """Verify fee lookup queries classify properly."""
    res = QueryClassifier.classify("How much does the Verified Certificate track cost?")
    assert res.canonical_topic == CanonicalTopic.CERTIFICATE_FEE
    assert res.is_supported is True


def test_quiz_policy_classification():
    """Verify quiz policy queries classify properly."""
    res = QueryClassifier.classify("How many weekly quizzes are there, and what if I miss one?")
    assert res.canonical_topic == CanonicalTopic.QUIZ_POLICY
    assert res.is_supported is True


def test_assessment_weights_classification():
    """Verify assessment weights queries classify properly."""
    res = QueryClassifier.classify("What are the assessment weights for the course?")
    assert res.canonical_topic == CanonicalTopic.ASSESSMENT_WEIGHTS
    assert res.is_supported is True


def test_refund_policy_unsupported_classification():
    """Verify refund inquiries are classified as REFUND_POLICY and marked unsupported."""
    res = QueryClassifier.classify("If I pay the Rs. 1,500 fee and drop the course in Week 2, how do I get a refund?")
    assert res.canonical_topic == CanonicalTopic.REFUND_POLICY
    assert res.is_supported is False


def test_contextual_follow_up_for_refund():
    """Verify follow-up turn context identifies refund intent when query is brief."""
    context = [
        {"role": "user", "content": "How much does the Verified Certificate cost?"},
        {"role": "assistant", "content": "The Verified Certificate Track costs Rs. 1,500."},
    ]
    res = QueryClassifier.classify("What happens if I drop the course in Week 2?", conversation_context=context)
    assert res.canonical_topic == CanonicalTopic.REFUND_POLICY
    assert res.is_supported is False


def test_sql_and_kubernetes_unsupported_classification():
    """Verify curriculum out-of-scope inquiries are classified and marked unsupported."""
    res = QueryClassifier.classify("Does this course teach SQL database indexing and Kubernetes deployment?")
    assert res.canonical_topic == CanonicalTopic.SQL_INDEXING_AND_KUBERNETES
    assert res.is_supported is False


def test_off_topic_classification():
    """Verify external trivia inquiries are classified as OFF_TOPIC and unsupported."""
    res = QueryClassifier.classify("Who won the cricket match last night?")
    assert res.canonical_topic == CanonicalTopic.OFF_TOPIC
    assert res.is_supported is False


def test_normalize_text():
    """Verify text normalization collapses whitespace and strips punctuation."""
    raw = "What is the MINIMUM score needed to pass??? (DPM-101)  "
    norm = normalize_text(raw)
    assert norm == "what is the minimum score needed to pass dpm 101"
