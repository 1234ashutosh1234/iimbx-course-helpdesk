"""Registry storing explicit metadata and authority rules for course documents.

Notice: Document authority and policy versioning are derived strictly from textual
metadata and academic declarations, NEVER from filesystem modification timestamps (mtime).
"""

from typing import Dict, List
from backend.knowledge.schemas import AuthorityLevel, DocumentMetadata

EXPECTED_DOCUMENTS: List[str] = [
    "01_course_handbook.txt",
    "02_grading_policy_v1.txt",
    "03_grading_policy_v2.txt",
    "04_exam_rules_and_faq.txt",
]

DOCUMENT_METADATA_REGISTRY: Dict[str, DocumentMetadata] = {
    "01_course_handbook.txt": DocumentMetadata(
        filename="01_course_handbook.txt",
        title="Course Handbook & Overview",
        version="1.0",
        last_updated="15 August 2026",
        status="Official Course Document",
        authority_level=AuthorityLevel.BASELINE,
        is_active=True,
        supersedes=None,
        topics_covered=[
            "course_overview",
            "weekly_schedule",
            "expected_effort",
            "discussion_forum_sla",
            "assessment_weights",
            "quiz_count",
            "certificate_tracks",
            "certificate_fee",
            "track_upgrade_deadline",
        ],
        contains_untrusted_content=False,
    ),
    "02_grading_policy_v1.txt": DocumentMetadata(
        filename="02_grading_policy_v1.txt",
        title="Grading & Late Submission Policy (Version 1)",
        version="1.0 (January 2026 Cohort)",
        last_updated="10 January 2026",
        status="SUPERSEDED / INACTIVE",
        authority_level=AuthorityLevel.DEPRECATED,
        is_active=False,
        supersedes=None,
        topics_covered=[
            "passing_criteria_v1",
            "late_submission_policy_v1",
            "capstone_deadline_v1",
        ],
        contains_untrusted_content=False,
    ),
    "03_grading_policy_v2.txt": DocumentMetadata(
        filename="03_grading_policy_v2.txt",
        title="Grading & Late Submission Policy (Version 2 - UPDATED)",
        version="2.0 (Effective October 2026)",
        last_updated="05 October 2026",
        status="CURRENT ACTIVE POLICY",
        authority_level=AuthorityLevel.ACTIVE_OVERRIDE,
        is_active=True,
        supersedes="02_grading_policy_v1.txt",
        topics_covered=[
            "passing_criteria_v2",
            "late_submission_policy_v2",
            "capstone_deadline_v2",
            "missed_quiz_drop_rule",
        ],
        contains_untrusted_content=False,
    ),
    "04_exam_rules_and_faq.txt": DocumentMetadata(
        filename="04_exam_rules_and_faq.txt",
        title="Final Exam Rules & Student Forum Excerpts",
        version="1.0 (October 2026)",
        last_updated="25 October 2026",
        status="Sections 1 & 2 Official; Section 3 Untrusted Forum Excerpt",
        authority_level=AuthorityLevel.BASELINE,
        is_active=True,
        supersedes=None,
        topics_covered=[
            "official_exam_date",
            "exam_duration",
            "exam_proctoring",
            "closed_book_rule",
            "photo_id_requirement",
            "hardware_requirements",
            "prohibited_devices",
            "browser_and_network_requirements",
        ],
        contains_untrusted_content=True,
    ),
}
