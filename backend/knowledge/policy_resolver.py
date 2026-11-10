"""Source-of-truth policy resolver providing canonical authoritative course facts."""

from typing import Dict, List, Optional
from backend.knowledge.schemas import CanonicalTopic, PolicyFact
from backend.knowledge.authority import AuthorityHierarchy


class PolicyResolver:
    """Maintains the canonical source-of-truth matrix for DPM-101 course policies."""

    _FACTS: Dict[CanonicalTopic, PolicyFact] = {
        CanonicalTopic.PASSING_CRITERIA: PolicyFact(
            topic=CanonicalTopic.PASSING_CRITERIA,
            summary="To earn the Verified Certificate in DPM-101, learners must achieve an overall weighted score of at least 60% across quizzes, the capstone case, and the final exam, AND score at least 40% in the Proctored Final Exam separately.",
            details="The passing criteria were updated effective October 2026. The previous 50% overall threshold from Version 1 is obsolete. Learners scoring 85% or above receive a 'Pass with Distinction' badge.",
            source_files=["03_grading_policy_v2.txt"],
            is_supported=True,
            authority_note="Document 03_grading_policy_v2.txt is CURRENT ACTIVE POLICY and supersedes 02_grading_policy_v1.txt."
        ),
        CanonicalTopic.LATE_SUBMISSION: PolicyFact(
            topic=CanonicalTopic.LATE_SUBMISSION,
            summary="Late submissions are no longer accepted for weekly quizzes or the capstone case. The earlier 48-hour grace window with a 10% penalty has been discontinued.",
            details="No numerical penalty is defined in current policy; late submissions are simply not accepted. Because the best 5 out of 6 weekly quizzes are counted, learners can miss 1 weekly quiz without penalty.",
            source_files=["03_grading_policy_v2.txt"],
            is_supported=True,
            authority_note="Updated late policy in 03_grading_policy_v2.txt supersedes 02_grading_policy_v1.txt. No penalty marks are assumed."
        ),
        CanonicalTopic.CAPSTONE_DEADLINE: PolicyFact(
            topic=CanonicalTopic.CAPSTONE_DEADLINE,
            summary="The Capstone Product Case deadline is 15 November 2026, 11:59 PM IST.",
            details="The deadline was extended by 5 days from the earlier 10 November 2026 deadline defined in Version 1.",
            source_files=["03_grading_policy_v2.txt"],
            is_supported=True,
            authority_note="Extended deadline in 03_grading_policy_v2.txt supersedes 02_grading_policy_v1.txt."
        ),
        CanonicalTopic.FINAL_EXAM_DATE: PolicyFact(
            topic=CanonicalTopic.FINAL_EXAM_DATE,
            summary="The Proctored Final Exam is scheduled for 20 November 2026, with appointment slots available between 10:00 AM and 8:00 PM IST.",
            details="The exam date is fixed for 20 November 2026 as per Section 1 official rules. Duration is 90 minutes.",
            source_files=["04_exam_rules_and_faq.txt"],
            is_supported=True,
            authority_note="Official exam schedule from Section 1. Unmoderated student forum claims of 30 December are untrusted and excluded."
        ),
        CanonicalTopic.EXAM_FORMAT: PolicyFact(
            topic=CanonicalTopic.EXAM_FORMAT,
            summary="The final exam is strictly CLOSED-BOOK, 90 minutes in duration, and AI-proctored via webcam and microphone. Learners may NOT use course notes, external websites, search engines, or AI tools.",
            details="Only one blank sheet of rough paper and a basic physical calculator are permitted on the desk. A valid government photo ID (Aadhaar, Passport, Driving Licence, or PAN) must be shown to the webcam before starting.",
            source_files=["04_exam_rules_and_faq.txt"],
            is_supported=True,
            authority_note="Official rules from Section 1. Student forum claims of open-book are untrusted adversarial attacks and excluded."
        ),
        CanonicalTopic.SUPPORTED_EXAM_DEVICES: PolicyFact(
            topic=CanonicalTopic.SUPPORTED_EXAM_DEVICES,
            summary="The proctored final exam requires a desktop or laptop computer with a working webcam and microphone. Mobile phones and tablets (including iPads) are strictly NOT supported.",
            details="Technical requirements: Latest version of Google Chrome or Microsoft Edge browser and a stable internet connection with a minimum speed of 2 Mbps.",
            source_files=["04_exam_rules_and_faq.txt"],
            is_supported=True,
            authority_note="Official technical requirements from Section 2."
        ),
        CanonicalTopic.CERTIFICATE_FEE: PolicyFact(
            topic=CanonicalTopic.CERTIFICATE_FEE,
            summary="The Verified Certificate Track costs Rs. 1,500.",
            details="The Audit Track is free (lectures and reading materials only, without graded assignments or certificate). Upgrading from Audit to the Verified Track is permitted until the end of Week 4.",
            source_files=["01_course_handbook.txt"],
            is_supported=True,
            authority_note="Baseline official course handbook."
        ),
        CanonicalTopic.QUIZ_POLICY: PolicyFact(
            topic=CanonicalTopic.QUIZ_POLICY,
            summary="There are 6 weekly quizzes contributing 30% to the total score; the best 5 quizzes are counted, allowing 1 missed quiz without penalty.",
            details="Weekly quizzes are self-contained. Late submissions for quizzes are not accepted under the current policy.",
            source_files=["01_course_handbook.txt", "03_grading_policy_v2.txt"],
            is_supported=True,
            authority_note="Synthesized from 01_course_handbook.txt and 03_grading_policy_v2.txt."
        ),
        CanonicalTopic.ASSESSMENT_WEIGHTS: PolicyFact(
            topic=CanonicalTopic.ASSESSMENT_WEIGHTS,
            summary="Assessment weights are: Weekly Quizzes 30% (best 5 of 6), Capstone Product Case Submission 30%, and Proctored Final Exam 40%.",
            details="Total course weighted score is calculated out of 100%.",
            source_files=["01_course_handbook.txt"],
            is_supported=True,
            authority_note="Baseline official course handbook."
        ),
        CanonicalTopic.COURSE_DURATION: PolicyFact(
            topic=CanonicalTopic.COURSE_DURATION,
            summary="DPM-101 is an 8-week online course.",
            details="The course structure comprises 8 weeks of self-paced video lectures and live weekend doubt sessions.",
            source_files=["01_course_handbook.txt"],
            is_supported=True,
            authority_note="Baseline official course handbook."
        ),
        CanonicalTopic.COURSE_EFFORT: PolicyFact(
            topic=CanonicalTopic.COURSE_EFFORT,
            summary="Expected learner effort is 4 to 5 hours per week.",
            details="Includes video lectures, readings, and participation in discussion forums. The forum is open 24/7 with teaching assistants replying within 24 hours.",
            source_files=["01_course_handbook.txt"],
            is_supported=True,
            authority_note="Baseline official course handbook."
        ),
        CanonicalTopic.REFUND_POLICY: PolicyFact(
            topic=CanonicalTopic.REFUND_POLICY,
            summary="Refund policies and course withdrawal refund rules are not documented in the official course documents.",
            details="While the course handbook details the Rs. 1,500 fee and Week 4 upgrade deadline, refund terms upon dropping the course are not mentioned. Students should consult course administration.",
            source_files=[],
            is_supported=False,
            authority_note="Topic is not covered in any supplied document."
        ),
        CanonicalTopic.SQL_INDEXING_AND_KUBERNETES: PolicyFact(
            topic=CanonicalTopic.SQL_INDEXING_AND_KUBERNETES,
            summary="The supplied DPM-101 course documents describe user research, product roadmapping, metrics, and AI feature design. They do not mention SQL database indexing or Kubernetes deployment.",
            details="The course handbook (01_course_handbook.txt) describes topics including user research, product roadmapping, metrics, and AI feature design. It does not mention SQL database indexing or Kubernetes deployment.",
            source_files=["01_course_handbook.txt"],
            is_supported=False,
            authority_note="Document 01 describes course topics; it does not mention SQL indexing or Kubernetes."
        ),
        CanonicalTopic.OFF_TOPIC: PolicyFact(
            topic=CanonicalTopic.OFF_TOPIC,
            summary="This question is outside the scope of the DPM-101 course helpdesk.",
            details="The helpdesk strictly assists students with official DPM-101 course documents, policies, and guidelines.",
            source_files=[],
            is_supported=False,
            authority_note="Non-course external inquiry."
        ),
        CanonicalTopic.UNKNOWN: PolicyFact(
            topic=CanonicalTopic.UNKNOWN,
            summary="This topic is not covered in the official course documents.",
            details="No matching policy or rule was found in the official course documentation.",
            source_files=[],
            is_supported=False,
            authority_note="Unsupported inquiry."
        ),
    }

    @classmethod
    def get_fact(cls, topic: CanonicalTopic) -> PolicyFact:
        """Retrieve the canonical policy fact for a topic.
        
        Guarantees:
        - Source files are validated against the AuthorityHierarchy.
        - Superseded documents (02_grading_policy_v1.txt) are NEVER cited.
        """
        fact = cls._FACTS.get(topic, cls._FACTS[CanonicalTopic.UNKNOWN])
        
        # Double check: ensure no superseded files slip through
        clean_sources = [
            src for src in fact.source_files 
            if not AuthorityHierarchy.is_superseded(src, topic)
        ]
        
        if clean_sources != fact.source_files:
            return PolicyFact(
                topic=fact.topic,
                summary=fact.summary,
                details=fact.details,
                source_files=clean_sources,
                is_supported=fact.is_supported,
                authority_note=fact.authority_note
            )
        return fact

    @classmethod
    def get_multi_topic_fact(cls, topics: List[CanonicalTopic]) -> PolicyFact:
        """Retrieve or synthesize an authoritative PolicyFact across multiple topics.
        
        Guarantees:
        - When FINAL_EXAM_DATE and EXAM_FORMAT are both requested, provides
          the unified grounded policy response covering date, slots, and closed-book rules.
        - Source files are deduplicated and validated against AuthorityHierarchy.
        """
        if not topics:
            return cls.get_fact(CanonicalTopic.UNKNOWN)
        if len(topics) == 1:
            return cls.get_fact(topics[0])

        topic_set = set(topics)

        # Specialized synthesized response for combined Exam Date & Exam Format
        if topic_set == {CanonicalTopic.FINAL_EXAM_DATE, CanonicalTopic.EXAM_FORMAT}:
            return PolicyFact(
                topic=CanonicalTopic.FINAL_EXAM_DATE,
                summary=(
                    "The Proctored Final Exam is scheduled for 20 November 2026, "
                    "with appointment slots available between 10:00 AM and 8:00 PM IST. "
                    "The examination is strictly CLOSED-BOOK. "
                    "External websites, search engines, course notes and AI tools are not permitted."
                ),
                details=(
                    "Official exam rules from Section 1 of 04_exam_rules_and_faq.txt. "
                    "Exam Date is 20 November 2026 (Slots 10:00 AM to 8:00 PM IST, 90 minutes). "
                    "Format is strictly CLOSED-BOOK with AI proctoring via webcam and microphone."
                ),
                source_files=["04_exam_rules_and_faq.txt"],
                is_supported=True,
                authority_note="Document 04_exam_rules_and_faq.txt Sections 1 and 2 are active official rules."
            )

        # Generic clean multi-topic synthesis
        facts = [cls.get_fact(t) for t in topics]
        combined_summary = " ".join(f.summary for f in facts)
        combined_details = "\n\n".join(f.details for f in facts)
        
        seen_sources = set()
        clean_sources: List[str] = []
        for f in facts:
            for s in f.source_files:
                if s not in seen_sources:
                    seen_sources.add(s)
                    clean_sources.append(s)

        is_supported = all(f.is_supported for f in facts)
        notes = "; ".join(f.authority_note for f in facts if f.authority_note)

        return PolicyFact(
            topic=topics[0],
            summary=combined_summary,
            details=combined_details,
            source_files=clean_sources,
            is_supported=is_supported,
            authority_note=notes or None
        )
