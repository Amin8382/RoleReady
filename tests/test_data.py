import json

import pytest

from roleready.data import common_record, group_id, normalize, prepare_data, split_for
from roleready.paths import digest
from roleready.retrieval import ranking_metrics


def test_duplicates_share_group_and_split():
    a, b = " Explain  database transactions? ", "explain database TRANSACTIONS?"
    assert normalize(a) == normalize(b)
    assert group_id(a) == group_id(b)
    assert split_for(a) == split_for(b)


def test_ranking_metrics():
    result = ranking_metrics(["a", "b", "c"], {"b", "c"}, 2)
    assert result["hit_rate_at_2"] == 1
    assert result["recall_at_2"] == 0.5
    assert result["mrr_at_2"] == 0.5
    assert 0 < result["ndcg_at_2"] < 1


def test_source_specific_metadata_is_preserved():
    source = {
        "dataset": "test",
        "revision": "abc",
        "source_url": "https://example.org",
        "publisher_license_metadata": "mit",
        "purpose": "evaluation_only",
    }
    record = common_record(
        {
            "question": "Explain a model registry",
            "reference_answer": "Tracks model versions",
            "question_category": "MLOps",
            "question_level": "Level 1",
            "expected_concepts": ["versioning"],
            "evaluation_rubric": {"excellent": "traceability"},
        },
        source,
        2,
    )
    assert record["reference_answer"] == "Tracks model versions"
    assert record["category"] == "MLOps"
    assert record["expected_concepts"] == ["versioning"]
    assert record["retrieval_allowed"] is False


def test_preparation_blocks_changed_raw_data(tmp_path, monkeypatch):
    monkeypatch.setattr("roleready.tracking.ROOT", tmp_path)
    source = {"dataset": "example", "cache_filename": "x.jsonl", "sha256": "wrong"}
    (tmp_path / "configs").mkdir()
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "configs/datasets.json").write_text(json.dumps([source]))
    (tmp_path / "data/raw/x.jsonl").write_text('{"question":"Explain a database"}\n')
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///" + str(tmp_path / "runs.db"))
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "checksum-test")
    with pytest.raises(ValueError, match="Raw source changed"):
        prepare_data(tmp_path)


def test_manifest_digest_changes_with_content(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("a")
    first = digest(path)
    path.write_text("b")
    assert digest(path) != first
