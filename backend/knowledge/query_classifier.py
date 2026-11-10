"""Deterministic query classification engine for student inquiries."""

import re
import unicodedata
from typing import List, Optional, Tuple, Dict, Any

from backend.knowledge.schemas import CanonicalTopic, ClassificationResult


def normalize_text(text: str) -> str:
    """Normalize text by folding case, removing punctuation, and collapsing whitespace."""
    if not text:
        return ""
    # Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", text).lower()
    # Replace punctuation with spaces
    text = re.sub(r"[?!.,;:\'\"()\[\]{}/\\`~@#$%^&*_\-+=<>|]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


class QueryClassifier:
    """Classifies user queries into canonical topics using deterministic patterns and heuristics."""

    # Compile regex pattern groups for deterministic high-precision matching
    _PATTERNS: Dict[CanonicalTopic, List[Tuple[re.Pattern, float]]] = {
        CanonicalTopic.PASSING_CRITERIA: [
            (re.compile(r"\b(minimum|passing|cutoff|cut off)\s+(score|mark|marks|percentage|percent|threshold)\b"), 0.95),
            (re.compile(r"\bhow\s+much\s+(do\s+i|must\s+i|to)\s+(need\s+to\s+)?score\s+to\s+pass\b"), 0.95),
            (re.compile(r"\bto\s+pass\s+(the\s+)?(course|dpm\s*101)\b"), 0.90),
            (re.compile(r"\b(pass|passing)\s+(criteria|threshold|requirement|rules)\b"), 0.95),
            (re.compile(r"\bpercentage\s+(is\s+)?required\s+for\s+(a\s+)?verified\s+certificate\b"), 0.95),
            (re.compile(r"\bpass\s+with\s+distinction\b"), 0.90),
        ],
        CanonicalTopic.LATE_SUBMISSION: [
            (re.compile(r"\b(submit|submission|submitting)\s+(the\s+)?(capstone|project|case|quiz|quizzes)?\s*(\d+\s*day|hours?|late)\b"), 0.95),
            (re.compile(r"\b(late\s+submission|submit\s+late|submitted\s+late)\b"), 0.95),
            (re.compile(r"\b(grace\s+(period|window)|10%\s+penalty|late\s+penalty)\b"), 0.95),
            (re.compile(r"\bwhat\s+happens\s+if\s+i\s+submit\b.*\blate\b"), 0.95),
            (re.compile(r"\bcan\s+i\s+submit\s+after\s+deadline\b"), 0.90),
        ],
        CanonicalTopic.CAPSTONE_DEADLINE: [
            (re.compile(r"\b(when\s+is\s+the\s+)?capstone\s+(product\s+case\s+)?(project\s+)?(due|deadline|date|submission\s+date)\b"), 0.95),
            (re.compile(r"\bdue\s+date\s+for\s+(the\s+)?capstone\b"), 0.95),
            (re.compile(r"\bcapstone\s+due\b"), 0.90),
            (re.compile(r"\bdeadline\s+for\s+(the\s+)?capstone\b"), 0.95),
        ],
        CanonicalTopic.FINAL_EXAM_DATE: [
            (re.compile(r"\b(when\s+is\s+(the\s+)?(proctored\s+)?(final\s+)?exam\b|exam\s+(date|schedule|timing|slots?))\b"), 0.95),
            (re.compile(r"\bwhen\s+(do\s+we\s+have|are\s+we\s+having|is|will\s+be|do\s+we\s+take)\s+(the\s+)?(proctored\s+)?(final\s+)?exam\b"), 0.95),
            (re.compile(r"\bwhen\s+is\s+it\s+scheduled\b"), 0.85),
            (re.compile(r"\bdate\s+of\s+(the\s+)?(final\s+)?exam\b"), 0.95),
            (re.compile(r"\b(final\s+)?exam\s+date\b"), 0.95),
        ],
        CanonicalTopic.EXAM_FORMAT: [
            (re.compile(r"\b(open\s*book|closed\s*book)\b"), 0.95),
            (re.compile(r"\bis\s+it\s+(open\s*book|closed\s*book)\b"), 0.95),
            (re.compile(r"\bis\s+the\s+(final\s+)?exam\s+(open|closed)\b"), 0.95),
            (re.compile(r"\b(date\s+and\s+format|format\s+and\s+date|exam\s+format|format\s+of\s+(the\s+)?(final\s+)?exam)\b"), 0.95),
            (re.compile(r"\b(notes|external\s+websites|search\s+engines|google|ai\s+tools|calculator|rough\s+paper)\s+during\s+(the\s+)?(exam|test)\b"), 0.95),
            (re.compile(r"\bcan\s+(i|we)\s+use\s+(notes|books|internet|ai|google)\b"), 0.95),
            (re.compile(r"\b(photo\s+id|aadhaar|passport|licence|pan\s+card)\s+(required|for\s+exam)\b"), 0.90),
            (re.compile(r"\bproctor(ed|ing)?\s+rules\b"), 0.90),
        ],
        CanonicalTopic.SUPPORTED_EXAM_DEVICES: [
            (re.compile(r"\b(ipad|tablet|tablets|mobile\s+phones?|cellphone|phone|laptop|desktop)\b.*(exam|test|proctored)"), 0.95),
            (re.compile(r"\b(take|attempt|write)\s+(the\s+)?(proctored\s+)?(final\s+)?exam\s+on\s+(my\s+)?(ipad|tablet|phone|mobile)\b"), 0.98),
            (re.compile(r"\b(hardware|device|system|browser|webcam|microphone)\s+requirements?\s+for\s+(the\s+)?exam\b"), 0.95),
            (re.compile(r"\bcan\s+i\s+(use|take\s+exam\s+on)\s+(an\s+)?(ipad|tablet|mobile)\b"), 0.95),
        ],
        CanonicalTopic.CERTIFICATE_FEE: [
            (re.compile(r"\b(how\s+much\s+(does\s+the\s+)?verified\s+certificate\s+(track\s+)?cost|certificate\s+(fee|cost|price))\b"), 0.95),
            (re.compile(r"\b(cost\s+of|fee\s+for)\s+(the\s+)?(verified\s+)?certificate\b"), 0.95),
            (re.compile(r"\b(upgrade|audit\s+track)\s+(to\s+verified|fee|deadline)\b"), 0.90),
            (re.compile(r"\b1500\s+(rupees|rs|inr)\b"), 0.85),
        ],
        CanonicalTopic.QUIZ_POLICY: [
            (re.compile(r"\b(how\s+many|number\s+of)\s+(weekly\s+)?quizzes\b"), 0.95),
            (re.compile(r"\bwhat\s+if\s+i\s+miss\s+(a|one)\s+(weekly\s+)?quiz\b"), 0.95),
            (re.compile(r"\b(missed|miss)\s+(a\s+)?quiz\b"), 0.90),
            (re.compile(r"\bbest\s+5\s+(of|out\s+of)\s+6\b"), 0.95),
            (re.compile(r"\bquiz\s+policy\b"), 0.90),
        ],
        CanonicalTopic.ASSESSMENT_WEIGHTS: [
            (re.compile(r"\b(assessment\s+weights?|weightage|grading\s+breakdown|evaluation\s+scheme)\b"), 0.95),
            (re.compile(r"\bpercentage\s+of\s+(quizzes|capstone|exam|each\s+component)\b"), 0.90),
            (re.compile(r"\bhow\s+is\s+(the\s+)?(final\s+)?grade\s+calculated\b"), 0.90),
        ],
        CanonicalTopic.COURSE_DURATION: [
            (re.compile(r"\b(how\s+long\s+is\s+the\s+course|duration\s+of\s+(the\s+)?course|how\s+many\s+weeks)\b"), 0.95),
            (re.compile(r"\bcourse\s+duration\b"), 0.95),
        ],
        CanonicalTopic.COURSE_EFFORT: [
            (re.compile(r"\b(how\s+many\s+hours\s+per\s+week|hours?\s+per\s+week|expected\s+effort|weekly\s+effort|time\s+commitment)\b"), 0.95),
        ],
        CanonicalTopic.REFUND_POLICY: [
            (re.compile(r"\b(refund|refunds|money\s+back|fee\s+refund|get\s+my\s+money\s+back)\b"), 0.95),
            (re.compile(r"\bdrop\s+(the\s+)?course.*(refund|money)\b"), 0.95),
            (re.compile(r"\bif\s+i\s+pay.*drop.*(refund|back)\b"), 0.95),
            (re.compile(r"\bcancellation\s+policy\b"), 0.90),
        ],
        CanonicalTopic.SQL_INDEXING_AND_KUBERNETES: [
            (re.compile(r"\b(sql|database\s+indexing|indexing|kubernetes|k8s|docker)\b"), 0.95),
            (re.compile(r"\bdoes\s+this\s+course\s+teach\s+(sql|kubernetes)\b"), 0.98),
        ],
        CanonicalTopic.OFF_TOPIC: [
            (re.compile(r"\b(cricket|match|football|soccer|weather|movie|president|prime\s+minister|stock\s+market|recipe)\b"), 0.95),
            (re.compile(r"\bwho\s+won\s+the\s+.*match\b"), 0.98),
            (re.compile(r"\btell\s+me\s+a\s+joke\b"), 0.95),
        ],
    }

    @classmethod
    def classify(
        cls, 
        query: str, 
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> ClassificationResult:
        """Classify a student query into a canonical topic.

        Args:
            query: The raw query string from the student.
            conversation_context: Optional prior turns [{'role': '...', 'content': '...'}]

        Returns:
            ClassificationResult containing topic, confidence, and supported status.
        """
        normalized = normalize_text(query)
        if not normalized:
            return ClassificationResult(
                canonical_topic=CanonicalTopic.UNKNOWN,
                confidence=0.0,
                matched_patterns=[],
                is_supported=False,
                canonical_topics=[CanonicalTopic.UNKNOWN],
            )

        # 1. Direct Pattern Evaluation on Current Query (collecting all high-confidence topics)
        matched_topics: Dict[CanonicalTopic, Tuple[float, List[str], int]] = {}

        for topic, rules in cls._PATTERNS.items():
            for pattern, score in rules:
                m = pattern.search(normalized)
                if m:
                    if topic not in matched_topics:
                        matched_topics[topic] = (score, [pattern.pattern], m.start())
                    else:
                        prev_score, prev_pats, prev_start = matched_topics[topic]
                        new_pats = list(prev_pats)
                        if pattern.pattern not in new_pats:
                            new_pats.append(pattern.pattern)
                        matched_topics[topic] = (
                            max(prev_score, score),
                            new_pats,
                            min(prev_start, m.start()),
                        )

        # 2. Context-Aware Evaluation for Follow-up Inquiries
        if conversation_context and (not matched_topics or CanonicalTopic.REFUND_POLICY in matched_topics):
            # Check if current query asks about dropping / refunding in reference to previous fee turn
            context_text = " ".join([turn.get("content", "") for turn in conversation_context[-2:]])
            norm_context = normalize_text(context_text)

            # If student says "What happens if I drop the course in Week 2?" or "How do I get a refund?"
            if any(term in normalized for term in ["drop", "cancel", "leave", "quit", "withdraw", "refund"]):
                if any(fee_term in norm_context for fee_term in ["1500", "fee", "cost", "certificate", "verified"]):
                    matched_topics[CanonicalTopic.REFUND_POLICY] = (
                        0.90,
                        ["context_fee_followup_refund"],
                        0,
                    )

        # 3. Resolve matched topics list
        if not matched_topics:
            canonical_topics = [CanonicalTopic.UNKNOWN]
            best_topic = CanonicalTopic.UNKNOWN
            best_confidence = 0.1
            matched_rules = []
        else:
            # Filter topics with strong match confidence
            strong_matches = {
                t: data for t, data in matched_topics.items() if data[0] >= 0.85
            }
            if not strong_matches:
                strong_matches = matched_topics

            # Sort topics by order of appearance in the student query
            canonical_topics = sorted(strong_matches.keys(), key=lambda t: strong_matches[t][2])
            best_topic = canonical_topics[0]
            best_confidence = max(strong_matches[t][0] for t in canonical_topics)
            matched_rules = [pat for t in canonical_topics for pat in strong_matches[t][1]]

        # 4. Determine if all topics are supported by the course documents
        is_supported = all(
            t not in {
                CanonicalTopic.REFUND_POLICY,
                CanonicalTopic.SQL_INDEXING_AND_KUBERNETES,
                CanonicalTopic.OFF_TOPIC,
                CanonicalTopic.UNKNOWN,
            }
            for t in canonical_topics
        )

        return ClassificationResult(
            canonical_topic=best_topic,
            confidence=best_confidence,
            matched_patterns=matched_rules,
            is_supported=is_supported,
            requires_context=bool(conversation_context),
            canonical_topics=canonical_topics,
        )
