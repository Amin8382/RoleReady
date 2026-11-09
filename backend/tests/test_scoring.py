import pytest
from backend.app.scoring.prometheus import PrometheusScorer
from backend.app.scoring.mock_scorer import MockScorer


def test_prometheus_regex_parser():
    scorer = PrometheusScorer()
    sample_output = """
    Scores:
    - Correctness: 4
    - Coverage: 5
    - Relevance: 4
    - Evidence and Structure: 4

    Evidence:
    - Candidate specifically mentioned IVF index and Product Quantization.
    - Demonstrated clear understanding of memory footprint trade-offs.

    Feedback: Very solid technical explanation. Next time mention HNSW graph comparisons.
    """

    parsed = scorer.parse_prometheus_output(sample_output)
    assert parsed["correctness"] == 4
    assert parsed["coverage"] == 5
    assert parsed["relevance"] == 4
    assert parsed["evidence_and_structure"] == 4
    assert parsed["overall_score"] == 4.25
    assert len(parsed["evidence"]) == 2
    assert "IVF" in parsed["evidence"][0]
    assert "HNSW" in parsed["feedback"]


def test_prometheus_regex_parser_resilience_to_irregular_format():
    scorer = PrometheusScorer()
    sample_output = """
    The model evaluation is:
    Correctness: 2/5
    Coverage: 2
    Relevance: 3
    Evidence: 1
    Feedback: The response lacks depth.
    """

    parsed = scorer.parse_prometheus_output(sample_output)
    assert parsed["correctness"] == 2
    assert parsed["coverage"] == 2
    assert parsed["relevance"] == 3
    assert parsed["evidence_and_structure"] == 1
    assert parsed["overall_score"] == 2.0


@pytest.mark.asyncio
async def test_mock_scorer_weak_vs_strong_output():
    scorer = MockScorer()

    # Weak answer (< 10 words)
    weak_res = await scorer.evaluate_answer(
        session_id="test",
        question_id="q1",
        question_text="How to scale FAISS?",
        target_skill="Vector Search",
        reference_criteria="IVF PQ index memory trade-offs",
        original_transcript="I don't know.",
        corrected_transcript="I don't know.",
    )
    assert weak_res.scores.overall_score <= 2.0
    assert "brief" in weak_res.feedback.lower()

    # Strong answer (> 30 words with keywords)
    strong_text = "To scale FAISS to 10M embeddings, I use IVF with Product Quantization (PQ) to reduce index memory footprint while balancing search latency."
    strong_res = await scorer.evaluate_answer(
        session_id="test",
        question_id="q1",
        question_text="How to scale FAISS?",
        target_skill="Vector Search",
        reference_criteria="IVF PQ index memory trade-offs",
        original_transcript=strong_text,
        corrected_transcript=strong_text,
    )
    assert strong_res.scores.overall_score >= 3.0
    assert len(strong_res.evidence) >= 1

