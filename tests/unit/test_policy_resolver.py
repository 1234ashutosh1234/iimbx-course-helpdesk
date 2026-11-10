"""Unit tests for PolicyResolver source-of-truth matrix."""

from backend.knowledge.schemas import CanonicalTopic
from backend.knowledge.policy_resolver import PolicyResolver


def test_passing_criteria_includes_60_and_40():
    """Verify passing criteria requires 60% overall and 40% in final exam separately."""
    fact = PolicyResolver.get_fact(CanonicalTopic.PASSING_CRITERIA)
    assert fact.is_supported is True
    assert "60%" in fact.summary
    assert "40%" in fact.summary
    assert "Proctored Final Exam" in fact.summary
    assert fact.source_files == ["03_grading_policy_v2.txt"]
    assert "02_grading_policy_v1.txt" not in fact.source_files


def test_old_50_percent_pass_rule_never_returned_as_current():
    """Verify the superseded 50% passing threshold is not reported as current policy."""
    fact = PolicyResolver.get_fact(CanonicalTopic.PASSING_CRITERIA)
    assert "overall weighted score of at least 50%" not in fact.summary
    assert "obsolete" in fact.details.lower() or "previous" in fact.details.lower()


def test_late_submission_discontinued_no_numerical_penalty_invented():
    """Verify late submissions are no longer accepted and no penalty marks are invented."""
    fact = PolicyResolver.get_fact(CanonicalTopic.LATE_SUBMISSION)
    assert fact.is_supported is True
    assert "no longer accepted" in fact.summary.lower()
    # Ensure obsolete 10% penalty is rejected
    assert "10% mark deduction applies" not in fact.summary
    # Ensure no invented zero marks claim
    assert "0 marks" not in fact.summary
    assert "zero marks" not in fact.summary
    assert fact.source_files == ["03_grading_policy_v2.txt"]


def test_capstone_deadline_is_15_november():
    """Verify capstone deadline is extended to 15 November 2026."""
    fact = PolicyResolver.get_fact(CanonicalTopic.CAPSTONE_DEADLINE)
    assert fact.is_supported is True
    assert "15 November 2026" in fact.summary
    assert "11:59 PM IST" in fact.summary
    assert fact.source_files == ["03_grading_policy_v2.txt"]


def test_exam_is_closed_book_and_scheduled_20_november():
    """Verify exam is closed-book on 20 November 2026, rejecting injection claims."""
    date_fact = PolicyResolver.get_fact(CanonicalTopic.FINAL_EXAM_DATE)
    assert "20 November 2026" in date_fact.summary
    assert "30 December" not in date_fact.summary
    assert date_fact.source_files == ["04_exam_rules_and_faq.txt"]

    format_fact = PolicyResolver.get_fact(CanonicalTopic.EXAM_FORMAT)
    assert "strictly CLOSED-BOOK" in format_fact.summary
    assert "OPEN-BOOK" not in format_fact.summary
    assert format_fact.source_files == ["04_exam_rules_and_faq.txt"]


def test_device_restrictions_retrieved():
    """Verify mobile and tablet restrictions are explicitly stated."""
    fact = PolicyResolver.get_fact(CanonicalTopic.SUPPORTED_EXAM_DEVICES)
    assert fact.is_supported is True
    assert "desktop or laptop" in fact.summary.lower()
    assert "mobile phones and tablets" in fact.summary.lower()
    assert "not supported" in fact.summary.lower()
    assert fact.source_files == ["04_exam_rules_and_faq.txt"]


def test_certificate_fee_retrieved():
    """Verify certificate track fee is Rs. 1,500."""
    fact = PolicyResolver.get_fact(CanonicalTopic.CERTIFICATE_FEE)
    assert fact.is_supported is True
    assert "1,500" in fact.summary or "1500" in fact.summary
    assert fact.source_files == ["01_course_handbook.txt"]


def test_quiz_policy_and_missed_quiz():
    """Verify 6 quizzes, best 5 counted, 1 can be missed without penalty."""
    fact = PolicyResolver.get_fact(CanonicalTopic.QUIZ_POLICY)
    assert fact.is_supported is True
    assert "6 weekly quizzes" in fact.summary
    assert "best 5" in fact.summary
    assert "1" in fact.summary and "missed" in fact.summary
    assert "01_course_handbook.txt" in fact.source_files
    assert "03_grading_policy_v2.txt" in fact.source_files


def test_assessment_weights_retrieved():
    """Verify 30% quizzes, 30% capstone, 40% exam."""
    fact = PolicyResolver.get_fact(CanonicalTopic.ASSESSMENT_WEIGHTS)
    assert fact.is_supported is True
    assert "Quizzes 30%" in fact.summary
    assert "Capstone" in fact.summary and "30%" in fact.summary
    assert "Final Exam 40%" in fact.summary
    assert fact.source_files == ["01_course_handbook.txt"]


def test_unsupported_topics_flagged():
    """Verify refund policy, SQL/Kubernetes, and off-topic inquiries are flagged unsupported."""
    refund_fact = PolicyResolver.get_fact(CanonicalTopic.REFUND_POLICY)
    assert refund_fact.is_supported is False
    assert refund_fact.source_files == []

    sql_fact = PolicyResolver.get_fact(CanonicalTopic.SQL_INDEXING_AND_KUBERNETES)
    assert sql_fact.is_supported is False

    off_topic = PolicyResolver.get_fact(CanonicalTopic.OFF_TOPIC)
    assert off_topic.is_supported is False
    assert off_topic.source_files == []
