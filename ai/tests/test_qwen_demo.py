import json
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from roleready_ai.datasets import load_jsonl
from roleready_ai.generation import validate_evidence, validate_questions
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


@pytest.mark.parametrize("timeout", [0, 601])
def test_demo_rejects_unbounded_timeout_before_contacting_service(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        run(model="missing", base_url="http://localhost:11434/v1", output=tmp_path,
            fixtures=FIXTURES, timeout=timeout)


def test_published_synthetic_outputs_replay_against_exact_train_fixtures():
    """Replay artifact integrity/structure, never infer model quality from this test."""
    path = FIXTURES.parents[1] / "evaluation/mission002/synthetic_samples.json"
    samples = json.loads(path.read_text(encoding="utf-8"))
    scenarios = {s["scenario_id"]: s for s in json.loads((FIXTURES / "scenarios.json").read_text())}
    bank = {r.record_id: r for r in load_jsonl(FIXTURES / "questions.train.jsonl")}
    for name, digest in samples["fixture_sha256"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest
    assert {(r["scenario_id"], r["retrieval"]) for r in samples["runs"]} == {
        (scenario, mode) for scenario in scenarios for mode in ("lexical", "bge-faiss")}
    assert len(samples["runs"]) == 6
    for run in samples["runs"]:
        scenario = scenarios[run["scenario_id"]]
        source_ids = {hit["source_id"] for hit in run["retrieved_sources"]}
        assert source_ids == set(run["generation"]["retrieved_source_ids"])
        for hit in run["retrieved_sources"]:
            record = bank[hit["source_id"]]
            assert record.split == "train" and hit["question"] == record.question
            assert hit["reference_answer"] is None  # Unreviewed answers never enter the prompt.
        raw = [{k: v for k, v in q.items() if k != "question_id"} for q in run["generation"]["questions"]]
        questions = validate_questions({"questions": raw}, allowed_source_ids=source_ids,
                                       experience_level=scenario["experience_level"])
        validate_evidence(questions, cv_text=scenario["cv_text"], job_description=scenario["job_description"])
        assert len(questions) == 7 and run["generation"]["model_id"] == samples["served_model"]
