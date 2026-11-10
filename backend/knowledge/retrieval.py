"""Deterministic evidence retrieval engine grounded in official course documents."""

import hashlib
from typing import Dict, List, Optional, Any

from backend.knowledge.schemas import (
    CanonicalTopic,
    EvidenceObject,
    CorpusState,
    ClassificationResult,
)
from backend.knowledge.document_loader import DocumentLoader
from backend.knowledge.authority import AuthorityHierarchy
from backend.knowledge.policy_resolver import PolicyResolver
from backend.knowledge.query_classifier import QueryClassifier, normalize_text


class RetrievalEngine:
    """Retrieves authoritative, grounded evidence for student inquiries."""

    def __init__(self, course_docs_dir: Optional[str] = None):
        """Initialize the retrieval engine and load the official corpus.
        
        Args:
            course_docs_dir: Optional path to course_docs folder.
        """
        self.loader = DocumentLoader(course_docs_dir)
        self.corpus_state: CorpusState = self.loader.load_corpus()

    @property
    def corpus_version(self) -> str:
        """Return the cryptographic digest of the loaded course corpus."""
        return self.corpus_state.corpus_version_hash

    def _compute_intent_id(
        self,
        topic_or_topics: Any,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        normalized_query: str = ""
    ) -> str:
        """Generate a deterministic intent identifier for caching in Part 4.
        
        Guarantees:
        - The same canonical topic across paraphrases yields the same intent identifier.
        - Multi-intent queries sort topics canonically so ordering in query does not alter intent_id.
        - Context-sensitive questions include a context digest to prevent cross-session collision.
        """
        if isinstance(topic_or_topics, (list, tuple, set)):
            topics_key = "+".join(sorted(t.value for t in topic_or_topics))
        elif hasattr(topic_or_topics, "value"):
            topics_key = topic_or_topics.value
        else:
            topics_key = str(topic_or_topics)

        if not conversation_context:
            return f"intent:{topics_key}"
        
        # When context is present, hash the prior 2 conversation turns
        ctx_tokens = [
            f"{turn.get('role', '')}:{normalize_text(turn.get('content', ''))}"
            for turn in conversation_context[-2:]
        ]
        context_str = "|".join(ctx_tokens)
        ctx_hash = hashlib.sha256(context_str.encode("utf-8")).hexdigest()[:12]
        return f"intent:{topics_key}:ctx:{ctx_hash}"

    def retrieve(
        self,
        question: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> EvidenceObject:
        """Retrieve authoritative evidence for a question, enforcing policy hierarchy.

        Args:
            question: Student's query string.
            conversation_context: Optional list of previous conversation turns.

        Returns:
            EvidenceObject containing grounded facts, source filenames, and authority status.
        """
        classification: ClassificationResult = QueryClassifier.classify(
            question, conversation_context
        )
        topics = classification.canonical_topics or [classification.canonical_topic]
        primary_topic = topics[0]
        norm_query = normalize_text(question)
        intent_id = self._compute_intent_id(topics, conversation_context, norm_query)

        # 1. Handle Unsupported & Out-of-Scope Inquiries
        if not classification.is_supported or any(
            t in {
                CanonicalTopic.REFUND_POLICY,
                CanonicalTopic.SQL_INDEXING_AND_KUBERNETES,
                CanonicalTopic.OFF_TOPIC,
                CanonicalTopic.UNKNOWN,
            }
            for t in topics
        ):
            fact = PolicyResolver.get_multi_topic_fact(topics)
            return EvidenceObject(
                question=question,
                canonical_topic=primary_topic,
                canonical_topics=topics,
                is_supported=False,
                evidence=fact.summary,
                source_files=fact.source_files,
                authority_status="UNSUPPORTED_TOPIC",
                corpus_version=self.corpus_version,
                confidence=classification.confidence,
                intent_id=intent_id,
                metadata={
                    "authority_note": fact.authority_note,
                    "matched_patterns": classification.matched_patterns,
                    "requires_context": classification.requires_context,
                    "all_topics": [t.value for t in topics],
                }
            )

        # 2. Retrieve Authoritative Policy Fact
        fact = PolicyResolver.get_multi_topic_fact(topics)

        # Verify no superseded source files exist
        valid_sources = [
            src for src in fact.source_files
            if not any(AuthorityHierarchy.is_superseded(src, t) for t in topics)
        ]

        # Extract filtered, authoritative text from the source files
        authoritative_snippets: List[str] = [fact.summary]
        for src in valid_sources:
            loaded_doc = self.corpus_state.documents.get(src)
            if loaded_doc:
                # Strictly filter out unmoderated student comments from 04_exam_rules_and_faq.txt
                clean_text = AuthorityHierarchy.filter_authoritative_content(
                    src, loaded_doc.content
                )
                # Keep snippet concise
                authoritative_snippets.append(f"[{src}] {clean_text[:400]}...")

        evidence_text = "\n\n".join(authoritative_snippets)

        return EvidenceObject(
            question=question,
            canonical_topic=primary_topic,
            canonical_topics=topics,
            is_supported=True,
            evidence=evidence_text,
            source_files=valid_sources,
            authority_status="AUTHORITATIVE_ACTIVE_POLICY",
            corpus_version=self.corpus_version,
            confidence=classification.confidence,
            intent_id=intent_id,
            metadata={
                "authority_note": fact.authority_note,
                "matched_patterns": classification.matched_patterns,
                "requires_context": classification.requires_context,
                "details": fact.details,
                "all_topics": [t.value for t in topics],
            }
        )
