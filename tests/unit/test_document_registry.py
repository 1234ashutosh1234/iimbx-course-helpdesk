"""Unit tests for DocumentRegistry."""

from backend.knowledge.schemas import AuthorityLevel
from backend.knowledge.document_registry import (
    DOCUMENT_METADATA_REGISTRY,
    EXPECTED_DOCUMENTS,
)


def test_registry_contains_all_expected_documents():
    """Verify registry has explicit entries for all 4 course files."""
    assert set(EXPECTED_DOCUMENTS) == set(DOCUMENT_METADATA_REGISTRY.keys())
    assert len(DOCUMENT_METADATA_REGISTRY) == 4


def test_v2_marked_active_and_supersedes_v1():
    """Verify Document 03 is marked active override and supersedes Document 02."""
    meta_v2 = DOCUMENT_METADATA_REGISTRY["03_grading_policy_v2.txt"]
    assert meta_v2.authority_level == AuthorityLevel.ACTIVE_OVERRIDE
    assert meta_v2.is_active is True
    assert meta_v2.supersedes == "02_grading_policy_v1.txt"
    assert "CURRENT ACTIVE POLICY" in meta_v2.status


def test_v1_marked_deprecated_and_inactive():
    """Verify Document 02 is marked deprecated and inactive."""
    meta_v1 = DOCUMENT_METADATA_REGISTRY["02_grading_policy_v1.txt"]
    assert meta_v1.authority_level == AuthorityLevel.DEPRECATED
    assert meta_v1.is_active is False
    assert "SUPERSEDED" in meta_v1.status


def test_exam_rules_flagged_with_untrusted_content():
    """Verify Document 04 is identified as containing untrusted student content."""
    meta_exam = DOCUMENT_METADATA_REGISTRY["04_exam_rules_and_faq.txt"]
    assert meta_exam.contains_untrusted_content is True
    assert meta_exam.is_active is True


def test_course_handbook_baseline_authority():
    """Verify Document 01 has baseline authority for course scope and fees."""
    meta_handbook = DOCUMENT_METADATA_REGISTRY["01_course_handbook.txt"]
    assert meta_handbook.authority_level == AuthorityLevel.BASELINE
    assert meta_handbook.is_active is True
    assert "certificate_fee" in meta_handbook.topics_covered
    assert "assessment_weights" in meta_handbook.topics_covered
