import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from roleready_ai.datasets import load_jsonl
from roleready_ai.qwen_demo import run, cached_bge_snapshot
from roleready_ai.retrieval import LexicalRetriever, BGE_MODEL, BGE_REVISION, load_embedding_model

FIXTURES = Path(__file__).resolve().parents[1] / "examples/mission002"


def test_demo_fixtures_are_synthetic_train_only_and_role_filtered():
    records = load_jsonl(FIXTURES / "questions.train.jsonl")
    assert len(records) == len({record.record_id for record in records}) == 18
    assert all(record.split == "train" and record.source_id == "mission002-synthetic" for record in records)
    scenarios = json.loads((FIXTURES / "scenarios.json").read_text())
    assert len(scenarios) == 3
    retriever = LexicalRetriever(records)
    for scenario in scenarios:
        assert scenario["cv_text"].startswith("Synthetic candidate:")
        hits = retriever.search(query=scenario["job_description"], role=scenario["target_role"], k=8)
        assert len(hits) == 8
        assert all(hit.record.role == "general" or hit.record.role in scenario["target_role"] for hit in hits)


@pytest.mark.parametrize("base_url", ["https://example.com/v1", "http://remote.example/v1", "http://localhost/api", "http://user:secret@localhost/v1"])
def test_demo_refuses_remote_or_credentialed_endpoints(tmp_path, base_url):
    with pytest.raises(ValueError):
        run(model="missing", base_url=base_url, output=tmp_path, fixtures=FIXTURES)


def test_demo_never_implicitly_downloads_a_missing_model(monkeypatch, tmp_path):
    calls = []
    def api(origin, path, data=None):
        calls.append(path)
        return {"models": []}
    monkeypatch.setattr("roleready_ai.qwen_demo.local_api", api)
    with pytest.raises(ValueError, match="never pulls"):
        run(model="missing", base_url="http://localhost:11434/v1", output=tmp_path, fixtures=FIXTURES)
    assert calls == ["/api/tags"]


def test_offline_bge_reuses_mission001_subset_not_other_weight_formats(monkeypatch):
    calls = []
    def snapshot(*args, **kwargs):
        calls.append(kwargs)
        return "cached-snapshot"
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot))
    assert cached_bge_snapshot() == "cached-snapshot"
    assert calls[0]["local_files_only"] is True
    assert "model.safetensors" in calls[0]["allow_patterns"]
    assert "*.bin" not in calls[0]["allow_patterns"]
    assert "onnx/*" not in calls[0]["allow_patterns"]


def test_standard_retriever_uses_cached_immutable_bge_revision(monkeypatch):
    calls = []
    def encoder(name, **kwargs):
        calls.append((name, kwargs))
        return "encoder"
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=encoder))
    assert load_embedding_model(BGE_MODEL) == "encoder"
    assert calls == [(BGE_MODEL, {"revision": BGE_REVISION})]
