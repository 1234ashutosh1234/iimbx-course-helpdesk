"""Authority hierarchy and policy precedence enforcement engine."""

import re
from typing import List, Optional, Set
from backend.knowledge.schemas import CanonicalTopic, AuthorityLevel
from backend.knowledge.document_registry import DOCUMENT_METADATA_REGISTRY

# Topics explicitly superseded by 03_grading_policy_v2.txt
SUPERSEDED_TOPICS_BY_V2: Set[CanonicalTopic] = {
    CanonicalTopic.PASSING_CRITERIA,
    CanonicalTopic.LATE_SUBMISSION,
    CanonicalTopic.CAPSTONE_DEADLINE,
}

# Authoritative source mapping for canonical topics
CANONICAL_TOPIC_AUTHORITATIVE_SOURCES = {
    CanonicalTopic.PASSING_CRITERIA: ["03_grading_policy_v2.txt"],
    CanonicalTopic.LATE_SUBMISSION: ["03_grading_policy_v2.txt"],
    CanonicalTopic.CAPSTONE_DEADLINE: ["03_grading_policy_v2.txt"],
    CanonicalTopic.FINAL_EXAM_DATE: ["04_exam_rules_and_faq.txt"],
    CanonicalTopic.EXAM_FORMAT: ["04_exam_rules_and_faq.txt"],
    CanonicalTopic.SUPPORTED_EXAM_DEVICES: ["04_exam_rules_and_faq.txt"],
    CanonicalTopic.CERTIFICATE_FEE: ["01_course_handbook.txt"],
    CanonicalTopic.QUIZ_POLICY: ["01_course_handbook.txt", "03_grading_policy_v2.txt"],
    CanonicalTopic.ASSESSMENT_WEIGHTS: ["01_course_handbook.txt"],
    CanonicalTopic.COURSE_DURATION: ["01_course_handbook.txt"],
    CanonicalTopic.COURSE_EFFORT: ["01_course_handbook.txt"],
    CanonicalTopic.REFUND_POLICY: [],
    CanonicalTopic.SQL_INDEXING_AND_KUBERNETES: ["01_course_handbook.txt"],
    CanonicalTopic.OFF_TOPIC: [],
    CanonicalTopic.UNKNOWN: [],
}


class AuthorityHierarchy:
    """Enforces document precedence, supersedence rules, and untrusted content exclusion."""

    @staticmethod
    def is_superseded(filename: str, topic: Optional[CanonicalTopic] = None) -> bool:
        """Check if a document is superseded, either globally or for a specific topic.
        
        Args:
            filename: The course document filename.
            topic: Optional canonical topic being queried.
            
        Returns:
            bool: True if the document is superseded for this inquiry.
        """
        metadata = DOCUMENT_METADATA_REGISTRY.get(filename)
        if not metadata:
            return True

        # Document 02 is globally superseded
        if metadata.authority_level == AuthorityLevel.DEPRECATED or not metadata.is_active:
            return True

        if topic and topic in SUPERSEDED_TOPICS_BY_V2 and filename != "03_grading_policy_v2.txt":
            # If asking about passing, late submission, or capstone deadline, only v2 is authoritative
            return True

        return False

    @staticmethod
    def get_authoritative_sources(topic: CanonicalTopic) -> List[str]:
        """Return the authoritative source filenames for a given topic.
        
        Guarantees that 02_grading_policy_v1.txt is NEVER returned as authoritative.
        """
        sources = CANONICAL_TOPIC_AUTHORITATIVE_SOURCES.get(topic, [])
        # Strict defensive filter: Never allow deprecated documents
        return [s for s in sources if not AuthorityHierarchy.is_superseded(s, topic)]

    @staticmethod
    def filter_authoritative_content(filename: str, raw_content: str) -> str:
        """Filter out unmoderated, non-authoritative, or untrusted sections from a document.

        Specifically, for 04_exam_rules_and_faq.txt:
        - Sections 1 & 2 are retained as authoritative official rules.
        - Section 3 (unmoderated student forum comments) is EXCLUDED from authoritative policy evidence.

        Args:
            filename: Document filename.
            raw_content: Full text of the document.

        Returns:
            str: Authoritative text only.
        """
        if filename != "04_exam_rules_and_faq.txt":
            return raw_content

        # Locate Section 3 header: "3. UNMODERATED STUDENT DISCUSSION FORUM COMMENTS"
        split_pattern = r"(?i)\n\s*3\.\s+UNMODERATED STUDENT DISCUSSION FORUM COMMENTS"
        parts = re.split(split_pattern, raw_content, maxsplit=1)
        
        if len(parts) > 1:
            # Retain Sections 1 & 2 only
            return parts[0].strip()
        
        return raw_content.strip()

    @staticmethod
    def extract_untrusted_forum_content(filename: str, raw_content: str) -> Optional[str]:
        """Extract unmoderated student comments separately for adversarial auditing or display."""
        if filename != "04_exam_rules_and_faq.txt":
            return None

        split_pattern = r"(?i)\n\s*3\.\s+UNMODERATED STUDENT DISCUSSION FORUM COMMENTS"
        parts = re.split(split_pattern, raw_content, maxsplit=1)
        if len(parts) > 1:
            return "3. UNMODERATED STUDENT DISCUSSION FORUM COMMENTS" + parts[1]
        return None
