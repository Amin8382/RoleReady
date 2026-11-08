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
        return {"questions": [
            {
                "text": f"Tell me about your approach to engineering problem number {i}.",
                "target_skill": "problem solving",
                "difficulty": "medium",
                "reason_for_asking": "Test relevant thinking",
                "reference_criteria": ["Concrete action", "Evidence"],
                "source_ids": [],
            } for i in range(1, 8)
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
