"""Knowledge and document intelligence package for IIMBx Course Helpdesk."""

from backend.knowledge.schemas import (
    CanonicalTopic,
    AuthorityLevel,
    DocumentMetadata,
    LoadedDocument,
    CorpusState,
    PolicyFact,
    ClassificationResult,
    EvidenceObject,
)
from backend.knowledge.document_loader import DocumentLoader
from backend.knowledge.document_registry import (
    DOCUMENT_METADATA_REGISTRY,
    EXPECTED_DOCUMENTS,
)
from backend.knowledge.authority import AuthorityHierarchy
from backend.knowledge.policy_resolver import PolicyResolver
from backend.knowledge.query_classifier import QueryClassifier, normalize_text
from backend.knowledge.retrieval import RetrievalEngine

__all__ = [
    "CanonicalTopic",
    "AuthorityLevel",
    "DocumentMetadata",
    "LoadedDocument",
    "CorpusState",
    "PolicyFact",
    "ClassificationResult",
    "EvidenceObject",
    "DocumentLoader",
    "DOCUMENT_METADATA_REGISTRY",
    "EXPECTED_DOCUMENTS",
    "AuthorityHierarchy",
    "PolicyResolver",
    "QueryClassifier",
    "normalize_text",
    "RetrievalEngine",
]
