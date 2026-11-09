from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class RubricScores(BaseModel):
    """
    1-5 scale practice performance rubric.
    Never represents hiring probability.
    """
    correctness: int = Field(..., ge=1, le=5, description="Factual and technical accuracy")
    coverage: int = Field(..., ge=1, le=5, description="Coverage of expected reference criteria")
    relevance: int = Field(..., ge=1, le=5, description="Focus on question prompt without tangential drift")
    evidence_and_structure: int = Field(..., ge=1, le=5, description="Clear reasoning, STAR structure, concrete examples")
    overall_score: float = Field(..., ge=1.0, le=5.0, description="Average practice score across the 4 dimensions")


class AnswerSubmitRequest(BaseModel):
    """
    Payload when the candidate submits an answer transcript.
    Allows Whisper original transcription + candidate corrected transcript.
    """
    question_id: str = Field(..., description="ID of question being answered")
    original_transcript: str = Field(..., description="Raw speech-to-text transcript from Whisper")
    corrected_transcript: str = Field(..., min_length=2, description="Candidate-reviewed or corrected transcript")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q1",
                "original_transcript": "I would use inverted file index and product quantize...",
                "corrected_transcript": "I would use an inverted file index (IVF) combined with product quantization (PQ) to compress vectors into RAM."
            }
        }
    )


class AnswerEvaluationResponse(BaseModel):
    """
    Evaluation output produced by the Prometheus 7B scoring engine.
    """
    session_id: str
    question_id: str
    original_transcript: str
    corrected_transcript: str
    rubric_version: str = Field(default="v1.0")
    scores: RubricScores
    evidence: List[str] = Field(default_factory=list, description="Specific phrases from candidate answer justifying the score")
    feedback: str = Field(..., description="Actionable recommendations for improvement")
    practice_notice: str = Field(
        default="Scores describe practice performance on this attempt, not the probability of being hired.",
        description="Standard ethical calibration disclaimer"
    )

