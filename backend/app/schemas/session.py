from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


class SessionCreateRequest(BaseModel):
    """Payload when creating a new preparation session."""
    target_role: str = Field(..., min_length=2, max_length=100, description="Target job title (e.g., ML Engineer)")
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.MID, description="Candidate target level")
    job_text: str = Field(..., min_length=20, max_length=20000, description="Pasted target job description text")
    cv_text: Optional[str] = Field(default=None, max_length=50000, description="Raw text of CV if not uploaded as a file")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_role": "Machine Learning Engineer",
                "experience_level": "mid",
                "job_text": "We are seeking a Machine Learning Engineer with experience in PyTorch, FAISS vector search, and LLM evaluation...",
                "cv_text": "Jane Doe - 3 years experience building NLP search engines and evaluation benchmarks in Python."
            }
        }
    )


class SessionCreateResponse(BaseModel):
    session_id: str
    target_role: str
    experience_level: str
    status: str
    message: str


class SessionAnalysisRequest(BaseModel):
    """Analysis input supplied by Amin's pipeline module."""
    strengths: List[str] = Field(..., description="Evidence-backed strengths identified between CV and job")
    requirements_not_evidenced: List[str] = Field(
        ...,
        description="Requirements not directly shown in CV (Note: missing evidence does not prove a missing skill)"
    )
    supporting_source_excerpts: List[str] = Field(
        default_factory=list,
        description="Source snippets from CV/Job that justify the alignment breakdown"
    )


class SessionAnalysisResponse(BaseModel):
    session_id: str
    target_role: str
    cv_text_preview: str
    job_text_preview: str
    strengths: List[str]
    requirements_not_evidenced: List[str]
    supporting_source_excerpts: List[str]


class SessionStateResponse(BaseModel):
    session_id: str
    user_id: str
    target_role: str
    experience_level: str
    status: str
    has_analysis: bool
    questions_count: int
    answers_count: int
    is_completed: bool

