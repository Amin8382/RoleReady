from pathlib import Path
import pytest
from roleready_ai.chat import ChatEndpoint, EndpointError
from roleready_ai.model_registry import MODELS, offline_report
from roleready_ai.scoring import PrometheusEvaluator, parse_absolute, absolute_prompt
from roleready_ai.voice import transcribe_english, synthesize_question


def test_registry_contains_five_distinct_models_without_loading_weights():
    assert len(MODELS) == len({m.key for m in MODELS}) == 5
    info = offline_report()
    assert len(info["models"]) == 5
    assert all(m["inference_verified"] is False for m in info["models"])


def test_remote_plain_http_is_rejected():
    with pytest.raises(EndpointError, match="HTTPS"):
        ChatEndpoint(base_url="http://example.com/v1", model="dummy")


def test_local_http_is_allowed():
    endpoint = ChatEndpoint(base_url="http://127.0.0.1:8001/v1", model="dummy")
    assert endpoint.base_url.endswith("/v1")


def test_prometheus_parser_and_invalid_rating():
    assert parse_absolute("Feedback: Strong detail. [RESULT] 4") == (4, "Strong detail.")
    with pytest.raises(ValueError):
        parse_absolute("Feedback: looks good [RESULT] 9")
    prompt = absolute_prompt(question="Explain SQL", answer="I used joins", reference_answer="Explain joins and indexes", criterion="correctness")
    assert "Score 5" in prompt
    assert "[correctness]" in prompt


class FakeJudge:
    model = "prometheus-mock"

    def __init__(self):
        self.calls = 0

    def complete(self, *, system: str, user: str, max_tokens: int = 1200) -> str:
        self.calls += 1
        assert "###Reference Answer" in user
        return "Feedback: Meets part of this criterion. [RESULT] 3"


def test_prometheus_four_dimensions_mock():
    judge = FakeJudge()
    result = PrometheusEvaluator(judge=judge).evaluate(
        question="Describe your SQL pipeline?",
        corrected_transcript="I tested queries and found slower joins",
        reviewed_reference_answer="Describe a specific SQL pipeline, tests and measured outcomes.",
    )
    assert judge.calls == 4
    assert result.average_score_1_to_5 == 3
    assert len(result.dimensions) == 4
    with pytest.raises(ValueError, match="HUMAN-REVIEWED"):
        PrometheusEvaluator(judge=judge).evaluate(
            question="Describe project", corrected_transcript="My answer",
            reviewed_reference_answer="",
        )


def test_audio_validation_without_downloading(tmp_path: Path):
    with pytest.raises(ValueError):
        transcribe_english(tmp_path / "nonexistent.wav")
    with pytest.raises(ValueError):
        synthesize_question("Hello.", tmp_path / "speech.mp3")
