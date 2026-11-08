from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from roleready.data import normalize


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SessionInput(StrictModel):
    cv_text: str = Field(min_length=40, max_length=24000)
    job_description: str = Field(min_length=40, max_length=16000)
    role: str = Field(min_length=2, max_length=120)
    experience_level: Literal["junior", "mid", "senior"] = "junior"


class Finding(StrictModel):
    title: str = Field(min_length=2, max_length=180)
    detail: str = Field(min_length=5, max_length=800)
    status: Literal["supported", "not_evidenced"]
    job_quote: str = Field(min_length=2, max_length=600)
    cv_quote: str | None = Field(default=None, max_length=600)


class Question(StrictModel):
    id: str = ""
    text: str = Field(min_length=15, max_length=2200)
    skill: str = Field(min_length=2, max_length=140)
    difficulty: Literal[1, 2, 3]
    category: Literal["technical", "behavioral", "project"]
    reason: str = Field(min_length=5, max_length=800)
    tip: str = Field(min_length=5, max_length=600)
    reference_criteria: list[str] = Field(min_length=1, max_length=8)
    reference_answer: str = Field(min_length=20, max_length=4000)
    source_ids: list[str] = Field(default_factory=list, max_length=10)


class Analysis(StrictModel):
    summary: str = Field(min_length=20, max_length=1500)
    findings: list[Finding] = Field(default_factory=list, max_length=12)
    questions: list[Question] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def distinct_questions(self):
        keys = [normalize(q.text) for q in self.questions]
        if len(set(keys)) != 7:
            raise ValueError("Seven distinct questions are required")
        return self


class AnswerInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=100)
    transcript: str = Field(min_length=10, max_length=8000)

    @field_validator("transcript")
    @classmethod
    def meaningful_text(cls, value):
        if len(value.split()) < 3:
            raise ValueError("Please provide at least three words")
        return value


class QuestionInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=100)


class Evaluation(StrictModel):
    score: int = Field(ge=1, le=5)
    feedback: str = Field(min_length=10, max_length=8000)
    rubric_version: str = "interview-v1"
    evaluator: str


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
