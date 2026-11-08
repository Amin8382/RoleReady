import json
from pathlib import Path
from roleready_ai.datasets import curate, normalize, partition, prepare, load_jsonl


def test_question_normalization_and_deterministic_partitions():
    assert normalize("  HOW   do YOU? ") == "how do you"
    assert partition("What is Python?") == partition(" WHAT is python!!! ")


def test_deduplicates_and_avoids_split_leakage():
    rows = [
        {"question": "Explain how you would design a reliable SQL pipeline?", "role": "Data Engineer"},
        {"question": "EXPLAIN how you would design a reliable SQL pipeline!", "role": "Data Engineer"},
        {"question": "Explain how you would design a reliable SQL pipeline?", "role": "ML Engineer"},
        {"question": "No", "role": "ML Engineer"},
    ]
    records, counts = curate(rows, source_id="example")
    assert counts["input"] == 4
    assert counts["duplicate"] == 1
    assert counts["invalid"] == 1
    assert len(records) == 2
    assert records[0].split == records[1].split
    assert all(not r.reviewed for r in records)


def test_manifest_and_output(tmp_path: Path):
    src = tmp_path / "questions.csv"
    src.write_text(
        "question,role,answer\n"
        "\"Tell me about a machine learning project you built?\",Machine Learning Engineer,My project\n"
        "\"Describe a production failure and your response?\",Machine Learning Engineer,I did something\n",
        encoding="utf-8",
    )
    out = tmp_path / "processed"
    manifest = prepare(src, out, source_id="sample", source_url="https://example.org/sample")
    assert manifest["counts"]["kept"] == 2
    assert manifest["license_verified"] is False
    assert len(manifest["source_sha256"]) == 64
    assert len(sum((load_jsonl(out / f"{s}.jsonl") for s in ("train", "validation", "test")), [])) == 2
    assert json.loads((out / "manifest.json").read_text())["source_id"] == "sample"
