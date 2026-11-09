import hashlib
import re
from typing import List
from .interface import BaseScorer
from ..schemas.answer import AnswerEvaluationResponse, RubricScores


class MockScorer(BaseScorer):
    """
    Deterministic realistic scorer for academic demos, local testing,
    and fallback when Prometheus 7B cannot run due to GPU/RAM constraints.
    """

    def __init__(self, rubric_version: str = "v1.0"):
        self.rubric_version = rubric_version

    async def evaluate_answer(
        self,
        session_id: str,
        question_id: str,
        question_text: str,
        target_skill: str,
        reference_criteria: str,
        original_transcript: str,
        corrected_transcript: str,
    ) -> AnswerEvaluationResponse:
        text = corrected_transcript.strip().lower()
        word_count = len(re.findall(r"\w+", text))
        # Match keywords including acronyms of 2+ letters (e.g. PQ, IVF, ML)
        keywords_in_ref = [w.lower() for w in re.findall(r"\b[A-Za-z0-9_-]{2,}\b", reference_criteria)]
        matched_keywords = [w for w in set(keywords_in_ref) if w in text]

        # Deterministic scoring based on content depth and reference coverage
        if word_count < 10:
            c, cov, r, s = 1, 1, 2, 1
            feedback = "The answer is too brief to demonstrate technical competence. State the core concept and explain the mechanism."
            evidence = ["Candidate provided minimal response"]
        elif len(matched_keywords) >= 3 or word_count >= 20:
            c, cov, r, s = 4, 4, 4, 4
            if len(matched_keywords) >= 4 or word_count > 60:
                c, cov, r, s = 5, 4, 5, 4
            feedback = f"Excellent technical explanation of {target_skill}. Clear conceptual clarity with sound reasoning. Consider citing precise benchmark metrics to reach perfection."
            evidence = [
                f"Referenced key concepts matching evaluation criteria: {', '.join(matched_keywords[:4])}",
                "Structured reasoning with logical problem-solving flow",
            ]
        elif word_count >= 10:
            c, cov, r, s = 3, 3, 3, 3
            feedback = f"Good foundational explanation for {target_skill}. To achieve a higher score, elaborate on trade-offs and concrete edge cases."
            evidence = [
                f"Matched key topics: {', '.join(matched_keywords[:2])}" if matched_keywords else "Basic terminology used",
                "Covers core question requirements",
            ]
        else:
            c, cov, r, s = 2, 2, 2, 2
            feedback = f"Identified basic aspects of {target_skill}, but lacks architectural detail and expected criteria coverage."
            evidence = ["General high-level overview"]

        overall = round((c + cov + r + s) / 4.0, 2)

        return AnswerEvaluationResponse(
            session_id=session_id,
            question_id=question_id,
            original_transcript=original_transcript,
            corrected_transcript=corrected_transcript,
            rubric_version=self.rubric_version,
            scores=RubricScores(
                correctness=c,
                coverage=cov,
                relevance=r,
                evidence_and_structure=s,
                overall_score=overall,
            ),
            evidence=evidence,
            feedback=feedback,
            practice_notice="Scores describe practice performance on this attempt, not the probability of being hired.",
        )
