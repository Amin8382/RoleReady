from abc import ABC, abstractmethod
from typing import Dict, Any
from ..schemas.answer import AnswerEvaluationResponse


class BaseScorer(ABC):
    """Abstract interface for answer scoring engines."""

    @abstractmethod
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
        """
        Evaluate candidate's answer using the shared 1-5 rubric.
        Returns a typed AnswerEvaluationResponse.
        """
        pass

