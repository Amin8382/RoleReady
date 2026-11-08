"""Versioned API contracts shared with frontend and AI modules."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

ExperienceLevel = Literal["entry", "junior", "mid", "senior"]

class SessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    target_role: str = Field(min_length=2, max_length=120)
    experience_level: ExperienceLevel
    cv_text: str = Field(min_length=30, max_length=20000)
    job_description: str = Field(min_length=30, max_length=20000)

class SkillEvidence(BaseModel):
    requirement: str
    job_excerpt: str
    cv_excerpt: str | None = None

class Analysis(BaseModel):
    strengths: list[SkillEvidence]
    requirements_not_evidenced: list[SkillEvidence]
    note: str

class InterviewQuestion(BaseModel):
    question_id: str
    text: str
    target_skill: str
    difficulty: Literal["easy", "medium", "hard"]
    reason_for_asking: str
    reference_criteria: list[str]
    source_ids: list[str]

class SessionResponse(BaseModel):
    session_id: str
    target_role: str
    experience_level: ExperienceLevel
    analysis: Analysis
    questions: list[InterviewQuestion]
    mode: Literal["keyword_baseline"] = "keyword_baseline"

class AnswerEvaluationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    question_text: str = Field(min_length=5)
    original_transcript: str = Field(min_length=1)
    corrected_transcript: str = Field(min_length=1)
    reference_criteria: list[str] = Field(min_length=1)
    rubric_version: Literal["1.0"] = "1.0"
