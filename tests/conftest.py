"""Synthetic contract fixtures. Never imported by application code."""

import pytest
from fastapi.testclient import TestClient

from roleready.api import create_app
from roleready.schemas import Analysis, Evaluation, ServiceError
from roleready.settings import Settings

QUESTION_TEXTS = [
    "How would you prevent data leakage when predicting customer churn?",
    "Explain how you would diagnose a slow database query.",
    "What would you consider before deploying a model to production?",
    "Describe how you would handle a disagreement about a project deadline.",
    "How would you validate a new data pipeline before release?",
    "Walk through how you would investigate an unexpected drop in model accuracy.",
    "Which tradeoffs would you discuss when choosing between two architectures?",
]
INPUTS = {
    "cv_text": "Synthetic candidate: built a Python pipeline with SQL validation and unit tests for a class project.",
    "job_description": "This test role requires Python, SQL, data validation, model evaluation, and clear communication.",
    "role": "Data Scientist",
    "experience_level": "junior",
}


def analysis_fixture():
    return Analysis.model_validate(
        {
            "summary": "Synthetic test analysis for verifying the application contract only.",
            "findings": [
                {
                    "title": "Python evidence",
                    "detail": "The provided text mentions Python.",
                    "status": "supported",
                    "job_quote": "Python",
                    "cv_quote": "Python",
                }
            ],
            "questions": [
                {
                    "id": f"q{i + 1}",
                    "text": text,
                    "skill": "Test skill",
                    "difficulty": 1,
                    "category": "technical",
                    "reason": "Synthetic test question.",
                    "tip": "Explain your reasoning.",
                    "reference_criteria": ["Explain assumptions", "Discuss validation"],
                    "reference_answer": "A synthetic reference explanation for contract testing only.",
                    "source_ids": [],
                }
                for i, text in enumerate(QUESTION_TEXTS)
            ],
        }
    )


class FixtureEngine:
    fail = False

    async def analyze(self, _inputs):
        return analysis_fixture()

    async def score(self, _question, _transcript):
        if self.fail:
            raise ServiceError("test_provider_failure", "Synthetic provider failure.", 502)
        return Evaluation(
            score=3,
            feedback="Synthetic test feedback: explain the validation approach in more detail.",
            evaluator="test-fixture",
        )


class FixtureVoice:
    def transcribe(self, _content):
        return "This is a synthetic transcript with a technical term."

    def speak(self, _text):
        return b"RIFF-test-fixture"


@pytest.fixture
def client(tmp_path):
    engine = FixtureEngine()
    settings = Settings(_env_file=None, state_dir=tmp_path, data_root=tmp_path, track_api_metrics=False)
    app = create_app(settings=settings, engine=engine, voice=FixtureVoice())
    with TestClient(app, headers={"Authorization": "Bearer local-development"}) as client:
        yield client
