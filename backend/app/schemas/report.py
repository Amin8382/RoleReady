from typing import List, Optional
from pydantic import BaseModel, Field
from .answer import AnswerEvaluationResponse


class PriorityImprovement(BaseModel):
    category: str = Field(..., description="E.g., Architecture, Technical Depth, Conciseness")
    gap_description: str = Field(..., description="Observed weakness across practice questions")
    action_item: str = Field(..., description="Concrete exercise or revision point before live interview")


class CheatSheetContent(BaseModel):
    key_strengths_summary: List[str]
    priority_improvements: List[PriorityImprovement]
    key_technical_concepts: List[str]
    recommended_answer_structures: List[str]
    suggested_next_practice_steps: List[str]


class FinalReportResponse(BaseModel):
    """
    Session final summary and cheat sheet content.
    Includes all 7 question evaluations.
    """
    session_id: str
    target_role: str
    experience_level: str
    seven_results: List[AnswerEvaluationResponse]
    average_session_score: float = Field(..., ge=1.0, le=5.0)
    priority_improvements: List[PriorityImprovement]
    cheat_sheet_content: CheatSheetContent
    pdf_location: Optional[str] = Field(default=None, description="Path or download URL for generated cheat sheet PDF")
    practice_notice: str = Field(
        default="Scores describe practice performance, not the probability of being hired."
    )


class DeleteDataResponse(BaseModel):
    status: str
    user_id: str
    deleted_sessions_count: int
    message: str

