"""Factual anchor validation for AI-generated answers."""

import re
from typing import List, Optional, Tuple
from backend.knowledge.schemas import CanonicalTopic
from backend.knowledge.policy_resolver import PolicyResolver


class ResponseValidator:
    """Validates that Gemini's generated answer contains mandatory factual anchors."""

    @classmethod
    def validate(cls, topic: CanonicalTopic, answer: str) -> Tuple[bool, Optional[str]]:
        """Validate generated text against canonical factual requirements.
        
        Args:
            topic: The canonical topic of the query.
            answer: The generated answer string.
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, failure_reason)
        """
        if not answer or not answer.strip():
            return False, "Answer is empty or whitespace only."

        text_lower = answer.lower()

        if topic == CanonicalTopic.PASSING_CRITERIA:
            # Check for obsolete 50% claim as current requirement first
            if re.search(r"\b(minimum|need|score|at\s+least|require[ds]?)\s+(of\s+)?50%", text_lower):
                return False, "Contradictory obsolete 50% passing score present as current rule."
            if "60%" not in answer and "60 percent" not in text_lower:
                return False, "Missing mandatory 60% overall passing score."
            if "40%" not in answer and "40 percent" not in text_lower:
                return False, "Missing mandatory 40% final exam cutoff."

        elif topic == CanonicalTopic.CAPSTONE_DEADLINE:
            if "10 november 2026" in text_lower and "superseded" not in text_lower and "extended" not in text_lower:
                return False, "Obsolete 10 November deadline cited as active."
            if not ("15 november 2026" in text_lower or "15th november 2026" in text_lower or "november 15, 2026" in text_lower):
                return False, "Missing or incorrect capstone deadline (must be 15 November 2026)."

        elif topic == CanonicalTopic.FINAL_EXAM_DATE:
            if "30 december" in text_lower:
                return False, "Adversarial false date '30 December' present in response."
            if not ("20 november 2026" in text_lower or "20th november 2026" in text_lower or "november 20, 2026" in text_lower):
                return False, "Missing or incorrect exam date (must be 20 November 2026)."

        elif topic == CanonicalTopic.EXAM_FORMAT:
            if "open-book" in text_lower or "open book" in text_lower:
                # Allowed only if explicitly stating it is NOT open book
                if not any(neg in text_lower for neg in ["not open", "not an open", "never open", "isn't open", "is strictly closed"]):
                    return False, "Adversarial open-book claim present in response."
            if "closed-book" not in text_lower and "closed book" not in text_lower:
                return False, "Missing mandatory closed-book rule."

        elif topic == CanonicalTopic.CERTIFICATE_FEE:
            if "1,500" not in answer and "1500" not in answer:
                return False, "Missing mandatory Rs. 1,500 certificate fee."

        elif topic == CanonicalTopic.LATE_SUBMISSION:
            # Check for invented numerical penalty (10% penalty or 0 marks) first
            if "10% deduction" in text_lower or "10% penalty" in text_lower or "10% mark deduction" in text_lower:
                return False, "Obsolete 10% late penalty cited as current policy."
            if "zero marks" in text_lower or "0 marks" in text_lower or "award zero" in text_lower:
                return False, "Invented zero-mark penalty claim."
            if not any(term in text_lower for term in ["no longer accepted", "not accepted", "discontinued", "no late submission"]):
                return False, "Missing statement that late submissions are no longer accepted."

        elif topic == CanonicalTopic.SUPPORTED_EXAM_DEVICES:
            if not ("desktop" in text_lower or "laptop" in text_lower):
                return False, "Missing desktop or laptop hardware requirement."
            if not ("tablet" in text_lower or "phone" in text_lower or "ipad" in text_lower):
                return False, "Missing tablet/mobile device restriction."

        elif topic == CanonicalTopic.QUIZ_POLICY:
            if "6" not in answer:
                return False, "Missing 6 quizzes count."
            if "5" not in answer or "best" not in text_lower:
                return False, "Missing best 5 quizzes rule."

        elif topic == CanonicalTopic.ASSESSMENT_WEIGHTS:
            if "30%" not in answer or "40%" not in answer:
                return False, "Missing assessment percentages (30% quizzes, 30% capstone, 40% exam)."

        return True, None

    @classmethod
    def validate_topics(cls, topics: List[CanonicalTopic], answer: str) -> Tuple[bool, Optional[str]]:
        """Validate generated text against multiple canonical topics.
        
        Args:
            topics: List of canonical topics.
            answer: The generated answer string.
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, failure_reason)
        """
        for t in topics:
            is_valid, reason = cls.validate(t, answer)
            if not is_valid:
                return False, f"[{t.value}] {reason}"
        return True, None

    @classmethod
    def get_fallback_answer(cls, topic: CanonicalTopic) -> str:
        """Provide a 100% grounded fallback answer directly from the trusted PolicyFact."""
        fact = PolicyResolver.get_fact(topic)
        return fact.summary

    @classmethod
    def get_fallback_answer_for_topics(cls, topics: List[CanonicalTopic]) -> str:
        """Provide a 100% grounded fallback answer for one or multiple canonical topics."""
        fact = PolicyResolver.get_multi_topic_fact(topics)
        return fact.summary
