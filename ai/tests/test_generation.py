from dataclasses import asdict
import pytest
from roleready_ai.datasets import QuestionRecord
from roleready_ai.retrieval import LexicalRetriever
from roleready_ai.generation import generate_questions, validate_questions


class FakeModel:
    model = "test-qwen-stand-in"

    def complete_json(self, *, system: str, user: str):
        assert "CV" in system
        assert "Machine Learning Engineer" in user
        texts = [
            "How did you validate the Python analytics project documented in your CV?",
            "How would you optimize a slow SQL join for this role?",
            "What tradeoffs would guide a production model deployment design?",
            "Describe how you would resolve a disagreement with a teammate.",
            "How would you identify data leakage before training a classifier?",
            "Which monitoring signals would reveal distribution drift?",
            "How would you explain an uncertain model prediction to a stakeholder?",
        ]
        return {"questions": [
            {
                "text": text,
                "target_skill": "problem solving",
                "difficulty": "medium",
                "reason_for_asking": "CV: [Python and SQL]; Job: [Python and production ML pipelines]. Practice the job requirement using documented CV context; missing ability is not inferred.",
                "reference_criteria": ["Concrete action", "Evidence"],
                "source_ids": [],
            } for text in texts
        ]}


def test_generation_with_mock_model_requires_no_gpu_or_api():
    record = QuestionRecord("q1", "How do you productionize a machine learning pipeline?", "Machine Learning Engineer", "sample", "train")
    result = generate_questions(
        model=FakeModel(),
        retriever=LexicalRetriever([record]),
        cv_text="I built projects using Python and SQL for analytics and machine learning.",
        job_description="We need a Machine Learning Engineer who knows Python and production ML pipelines.",
        role="Machine Learning Engineer", experience_level="mid",
    )
    assert len(result.questions) == 7
    assert result.mode == "qwen_retrieval"
    assert result.retrieved_source_ids == ["q1"]
    assert result.questions[0].question_id == "q1"


def test_hallucinated_source_is_rejected():
    question = {
        "text": "Explain how you would design a production-grade retrieval service.",
        "target_skill": "retrieval",
        "difficulty": "medium",
        "reason_for_asking": "Check design skills",
        "reference_criteria": ["Design tradeoffs"],
        "source_ids": ["invented"],
    }
    with pytest.raises(ValueError, match="non-retrieved"):
        validate_questions({"questions": [{**question, "text": question["text"] + str(i)} for i in range(7)]}, allowed_source_ids={"real"})


def test_duplicate_questions_are_rejected():
    q = {
        "text": "Explain how you would deploy a robust application.",
        "target_skill": "deployment", "difficulty": "medium",
        "reason_for_asking": "Role fit", "reference_criteria": ["Detail"], "source_ids": [],
    }
    with pytest.raises(ValueError, match="Duplicate"):
        validate_questions({"questions": [q] * 7}, allowed_source_ids=set())
