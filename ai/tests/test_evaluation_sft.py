import json
from pathlib import Path
from roleready_ai.datasets import QuestionRecord, write_jsonl
from roleready_ai.evaluation import summarize_predictions
from roleready_ai.sft import export_sft


def test_metrics_detect_invalid_source_ids():
    data = [{"target_role": "Engineer", "retrieved_source_ids": ["a"], "questions": [
        {"text": f"How would you approach scenario number {i}?", "source_ids": ["fake"] if i == 0 else []}
        for i in range(7)
    ]}]
    metrics = summarize_predictions(data)
    assert metrics["cases"] == 1
    assert metrics["valid_seven_distinct_rate"] == 1.0
    assert metrics["questions_citing_unretrieved_sources"] == 1


def test_sft_export_excludes_unreviewed_and_holdout(tmp_path: Path):
    src = tmp_path / "train.jsonl"
    out = tmp_path / "sft.jsonl"
    write_jsonl(src, [
        QuestionRecord("1", "Tell me about Python in production.", "ML Engineer", "x", "train", "Reviewed answer", True),
        QuestionRecord("2", "How do you build a reliable ETL pipeline?", "ML Engineer", "x", "train", "Not reviewed", False),
        QuestionRecord("3", "What is a good model validation process?", "ML Engineer", "x", "test", "Held out", True),
    ])
    assert export_sft(source=src, out=out) == 1
    result = [json.loads(line) for line in out.read_text().splitlines()]
    assert result[0]["record_id"] == "1"
    assert len(result) == 1
