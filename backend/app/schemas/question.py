from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QuestionDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionRecord(BaseModel):
    """
    Contract for each of the 7 prepared interview questions.
    Passed between Amin's pipeline, Oussema's backend, and Khaled's frontend.
    """
    question_id: str = Field(..., description="Unique question identifier (e.g., q1, q2)")
    text: str = Field(..., min_length=5, description="Interview question prompt text")
    target_skill: str = Field(..., description="Target skill or concept tested (e.g. Vector Search, RAG Architecture)")
    difficulty: QuestionDifficulty = Field(default=QuestionDifficulty.MEDIUM, description="Difficulty rating")
    reason_for_asking: str = Field(..., description="Why this question is relevant based on CV and Job gaps")
    reference_criteria: str = Field(
        ...,
        description="Ideal anchor points and concepts an evaluator expects in a strong answer"
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="Reference IDs from the question bank or dataset sources"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q1",
                "text": "How would you handle approximate nearest neighbor indexing when scaling to 10 million vectors?",
                "target_skill": "Vector Search & FAISS",
                "difficulty": "medium",
                "reason_for_asking": "Target job requires FAISS deployment at scale; CV highlights small-scale embeddings only.",
                "reference_criteria": "Mentions IVF/HNSW indexing trade-offs, quantisation (PQ), memory footprint, and latency vs recall balance.",
                "source_ids": ["ML_interview_bench_04"]
            }
        }
    )


class QuestionsCreateRequest(BaseModel):
    """Payload to store the 7 questions generated for a session."""
    questions: List[QuestionRecord] = Field(..., min_length=1, max_length=10)


class QuestionsResponse(BaseModel):
    session_id: str
    total_questions: int
    questions: List[QuestionRecord]

