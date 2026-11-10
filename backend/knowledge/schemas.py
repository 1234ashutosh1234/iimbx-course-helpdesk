"""Data schemas and type definitions for document intelligence and policy retrieval."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class CanonicalTopic(str, Enum):
    """Canonical topics representing student inquiry intents."""
    PASSING_CRITERIA = "PASSING_CRITERIA"
    LATE_SUBMISSION = "LATE_SUBMISSION"
    CAPSTONE_DEADLINE = "CAPSTONE_DEADLINE"
    FINAL_EXAM_DATE = "FINAL_EXAM_DATE"
    EXAM_FORMAT = "EXAM_FORMAT"
    SUPPORTED_EXAM_DEVICES = "SUPPORTED_EXAM_DEVICES"
    CERTIFICATE_FEE = "CERTIFICATE_FEE"
    QUIZ_POLICY = "QUIZ_POLICY"
    ASSESSMENT_WEIGHTS = "ASSESSMENT_WEIGHTS"
    COURSE_DURATION = "COURSE_DURATION"
    COURSE_EFFORT = "COURSE_EFFORT"
    REFUND_POLICY = "REFUND_POLICY"
    SQL_INDEXING_AND_KUBERNETES = "SQL_INDEXING_AND_KUBERNETES"
    OFF_TOPIC = "OFF_TOPIC"
    UNKNOWN = "UNKNOWN"


class AuthorityLevel(int, Enum):
    """Strict authority hierarchy levels for course documents."""
    DEPRECATED = 0            # Superseded historical policies (e.g., 02_grading_policy_v1.txt)
    BASELINE = 1              # Baseline official policies (e.g., 01_course_handbook.txt)
    ACTIVE_OVERRIDE = 2       # Active current overrides (e.g., 03_grading_policy_v2.txt)
    UNTRUSTED_CONTENT = -1    # Unmoderated forum comments (Section 3 of 04_exam_rules_and_faq.txt)


@dataclass(frozen=True)
class DocumentMetadata:
    """Explicit metadata describing a course document."""
    filename: str
    title: str
    version: str
    last_updated: str
    status: str
    authority_level: AuthorityLevel
    is_active: bool
    supersedes: Optional[str]
    topics_covered: List[str]
    contains_untrusted_content: bool = False


@dataclass
class LoadedDocument:
    """Represents an in-memory loaded document with cryptographic integrity hash."""
    filename: str
    content: str
    content_hash: str
    metadata: DocumentMetadata


@dataclass
class CorpusState:
    """State container for all loaded documents in the corpus."""
    documents: Dict[str, LoadedDocument]
    corpus_version_hash: str


@dataclass(frozen=True)
class PolicyFact:
    """Authoritative canonical fact derived from active official policies."""
    topic: CanonicalTopic
    summary: str
    details: str
    source_files: List[str]
    is_supported: bool = True
    authority_note: Optional[str] = None


@dataclass
class ClassificationResult:
    """Result of classifying a student query."""
    canonical_topic: CanonicalTopic
    confidence: float
    matched_patterns: List[str]
    is_supported: bool
    requires_context: bool = False


@dataclass
class EvidenceObject:
    """Structured evidence package returned by the retrieval engine."""
    question: str
    canonical_topic: CanonicalTopic
    is_supported: bool
    evidence: str
    source_files: List[str]
    authority_status: str
    corpus_version: str
    confidence: float
    intent_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
