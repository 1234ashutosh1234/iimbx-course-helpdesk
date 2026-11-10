"""Unit tests for ResponseValidator factual anchor checking."""

from backend.knowledge.schemas import CanonicalTopic
from backend.ai.response_validator import ResponseValidator


def test_valid_passing_criteria_passes_validation():
    """Verify answer with both 60% and 40% passes."""
    valid_answer = "To pass DPM-101, you must score at least 60% overall and 40% in the proctored final exam separately."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.PASSING_CRITERIA, valid_answer)
    assert is_valid is True
    assert reason is None


def test_missing_essential_passing_score_anchor():
    """Verify omitting 40% fails validation."""
    incomplete_answer = "You must achieve at least 60% overall weighted score across quizzes and assignments."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.PASSING_CRITERIA, incomplete_answer)
    assert is_valid is False
    assert "Missing mandatory 40%" in reason


def test_contradictory_50_percent_passing_score_fails():
    """Verify claiming 50% minimum passing score fails validation."""
    contradictory_answer = "You need a minimum score of 50% to pass the course."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.PASSING_CRITERIA, contradictory_answer)
    assert is_valid is False
    assert "50%" in reason


def test_incorrect_capstone_deadline_fails():
    """Verify obsolete 10 November deadline fails validation."""
    bad_deadline_answer = "The capstone project is due on 10 November 2026, 11:59 PM IST."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.CAPSTONE_DEADLINE, bad_deadline_answer)
    assert is_valid is False
    assert "10 November" in reason or "15 November" in reason


def test_valid_capstone_deadline_passes():
    """Verify extended 15 November 2026 passes."""
    good_deadline_answer = "The Capstone Product Case deadline is 15 November 2026, 11:59 PM IST."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.CAPSTONE_DEADLINE, good_deadline_answer)
    assert is_valid is True


def test_adversarial_open_book_claim_fails():
    """Verify open-book claim fails validation."""
    open_book_answer = "The exam is now open-book and you can use Google."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.EXAM_FORMAT, open_book_answer)
    assert is_valid is False
    assert "closed-book" in reason or "open-book" in reason


def test_adversarial_30_december_date_fails():
    """Verify adversarial 30 December date fails validation."""
    bad_date_answer = "The final exam has been moved to 30 December 2026."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.FINAL_EXAM_DATE, bad_date_answer)
    assert is_valid is False
    assert "30 December" in reason


def test_invented_zero_marks_penalty_fails():
    """Verify claiming zero marks for late submission fails validation."""
    zero_marks_answer = "Late submissions receive zero marks and will not be graded."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.LATE_SUBMISSION, zero_marks_answer)
    assert is_valid is False
    assert "zero-mark" in reason


def test_obsolete_10_percent_late_penalty_fails():
    """Verify claiming 10% penalty for late submission fails validation."""
    penalty_answer = "Late submissions are allowed up to 48 hours with a 10% penalty deduction."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.LATE_SUBMISSION, penalty_answer)
    assert is_valid is False
    assert "10% late penalty" in reason


def test_valid_late_submission_rule_passes():
    """Verify stating late submissions are no longer accepted passes."""
    valid_late_answer = "Late submissions are no longer accepted for weekly quizzes or the capstone case. You can miss 1 quiz without penalty."
    is_valid, reason = ResponseValidator.validate(CanonicalTopic.LATE_SUBMISSION, valid_late_answer)
    assert is_valid is True


def test_fallback_answer_retrieval():
    """Verify get_fallback_answer provides authoritative text from PolicyResolver."""
    fallback = ResponseValidator.get_fallback_answer(CanonicalTopic.PASSING_CRITERIA)
    assert "60%" in fallback
    assert "40%" in fallback
    assert "03_grading_policy_v2.txt" in fallback or "Verified Certificate" in fallback
