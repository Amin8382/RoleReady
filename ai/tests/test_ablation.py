"""Authored test fixtures only; no inference or genuine human ratings."""
import base64
from collections import Counter
import csv
import json
from pathlib import Path

import pytest

from roleready_ai.ablation import RequestJournal, request_metrics
from roleready_ai.experiment_protocol import ASSETS, CONDITIONS, SETTINGS, schedule, scenarios, check_serving
from roleready_ai.model import InvalidModelResponse, OpenAICompatibleQwen
from roleready_ai.question_review import export, import_reviews, analyze, paired_bootstrap
from roleready_ai.tracking import TrackingClient, digest, local_url, read_json, write_json


def test_frozen_design_is_balanced_disjoint_and_seed_paired():
    values = scenarios(ASSETS / "scenarios.json")
    plan = schedule(values)
    assert len(plan) == 288 and len({r["case_id"] for r in plan}) == 288
    assert Counter(r["condition"] for r in plan) == dict.fromkeys(CONDITIONS, 96)
    blocks = [tuple(r["condition"] for r in plan[i:i+3]) for i in range(0, 288, 3)]
    assert set(Counter(blocks).values()) == {16}
    for index in range(0, 288, 3):
        assert len({(r["scenario_id"], r["seed"]) for r in plan[index:index+3]}) == 1
    assert plan == schedule(values)


@pytest.mark.parametrize("url", ["https://remote.example", "http://remote.example", "http://user:pass@localhost", "http://localhost?token=x"])
def test_tracking_refuses_remote_or_credentialed_endpoints(url):
    with pytest.raises(ValueError, match="local"):
        local_url(url)


def test_request_records_preserve_invalid_envelope_and_seed(monkeypatch, tmp_path):
    raw = b'{"model":"qwen","choices":[{"finish_reason":"length","message":{"content":"broken"}}]}'
    observed = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return raw
    def call(request, **kwargs):
        observed.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr("roleready_ai.model.urlopen", call)
    journal = RequestJournal(tmp_path)
    model = OpenAICompatibleQwen(base_url="http://127.0.0.1:11434/v1", model="qwen", seed=17,
                                request_recorder=journal)
    with pytest.raises(InvalidModelResponse):
        model.complete_json(system="test", user="test")
    assert observed[0]["seed"] == 17
    assert base64.b64decode(journal.events[-1]["raw_response_base64"]) == raw
    assert read_json(tmp_path / "attempt-01-request_started.json")["payload"] == observed[0]
    assert request_metrics(journal.events)["input_tokens"] is None


def test_request_metrics_include_rejected_attempts_and_unknown_usage():
    events = [{"event": "request_started"}, {"event": "request_finished", "response": {
        "latency_ms": 11, "usage": {"prompt_tokens": 5, "completion_tokens": 7}}},
        {"event": "request_started"}, {"event": "request_finished", "response": {"latency_ms": 13}}]
    metrics = request_metrics(events)
    assert metrics["model_requests"] == 2 and metrics["retries"] == 1
    assert metrics["http_latency_ms"] == 24 and metrics["input_tokens"] is None


def test_constant_paired_difference_has_exact_interval():
    rows = [{"role": f"role-{i//4}", "difference": 1.25} for i in range(32)]
    report = paired_bootstrap(rows, repeats=100)
    assert report["independent_scenarios"] == 32
    assert report["ci95"] == report["ci98_33_bonferroni"] == [1.25, 1.25]


def review_fixture(tmp_path):
    output = tmp_path / "experiment"
    write_json(output / "freeze.json", {"freeze_sha256": "frozen-test-only"})
    for condition in CONDITIONS:
        case = {"ordinal": 0, "scenario_id": "abl-01-entry", "seed": 17,
                "condition": condition, "case_id": "test-" + condition}
        result = {"case_id": case["case_id"], "case": case, "status": "structural_pass",
            "retrieved_sources": [] if condition == "none" else [{"source_id": "doc-private", "question": "Authored source fixture"}],
            "generation": {"questions": [{"question_id": f"q{i}", "text": f"How would you validate metric {i}?",
                "reference_criteria": ["The answer should check units."],
                "source_ids": [] if condition == "none" else ["doc-private"]} for i in range(1,8)]}}
        write_json(output / "cases" / case["case_id"] / "result.json", result)
    bundle = tmp_path / "bundle"
    export(output, bundle)
    return bundle


def test_blinded_core_hides_condition_citations_and_private_keys(tmp_path):
    bundle = review_fixture(tmp_path)
    text = (bundle / "reviewer-1/core.csv").read_text(encoding="utf-8")
    assert "bge-faiss" not in text and "doc-private" not in text and "condition" not in text
    mapping = read_json(bundle / "PRIVATE_KEY.json")
    assert set(mapping["reviewers"]) == {"1", "2"}
    assert (bundle / "reviewer-1/core.csv").read_bytes() != (bundle / "reviewer-2/core.csv").read_bytes()
    report = analyze(bundle, [])
    assert report["quality_metrics"] is None and report["paired_analysis"] is None


def test_import_never_promotes_unjudged_or_agent_rows(tmp_path):
    bundle = review_fixture(tmp_path)
    result = import_reviews(bundle, bundle / "reviewer-1/core.csv", reviewer_number=1)
    assert result["approved"] == []
    path = tmp_path / "completed/core.csv"
    path.parent.mkdir()
    with (bundle / "reviewer-1/core.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows, fields = list(reader), reader.fieldnames
    rows[0].update(status="agent_provisional", rating="5", reviewer="agent", reviewed_at="2026-11-22")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    assert import_reviews(bundle, path, reviewer_number=1)["approved"] == []
    rows[0].update(status="human_reviewed", reviewer="", reviewed_at="")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError, match="reviewer"):
        import_reviews(bundle, path, reviewer_number=1)


def test_no_rag_has_no_grounding_review_rows(tmp_path):
    bundle = review_fixture(tmp_path)
    mapping = read_json(bundle / "PRIVATE_KEY.json")["reviewers"]["1"]
    none_ids = {k for k, v in mapping.items() if v["case"]["condition"] == "none"}
    with (bundle / "reviewer-1/grounding.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 14 and not none_ids & {r["blind_id"] for r in rows}


def test_serving_parameters_cannot_silently_change():
    show = {"details": {"family": "qwen35", "quantization_level": "Q4_K_M"},
            "parameters": "temperature 0.2\ntop_p 0.95\ntop_k 20\npresence_penalty 1.5\nnum_ctx 8192\nnum_predict 4096"}
    check_serving(show)
    show["parameters"] = show["parameters"].replace("8192", "4096")
    with pytest.raises(ValueError, match="num_ctx"):
        check_serving(show)


def test_runner_checkpoints_resumes_and_passes_identical_seed_and_contract(monkeypatch, tmp_path):
    from io import BytesIO
    from roleready_ai import ablation
    from roleready_ai.retrieval import EmptyRetriever
    from roleready_ai.generation import EVIDENCE_PURPOSE
    from roleready_ai.experiment_protocol import QWEN
    captured = []
    def response(request, **kwargs):
        body = json.loads(request.data)
        captured.append(body)
        text = body["messages"][1]["content"]
        context = json.loads(text[text.rfind("\n{") + 1:])
        assert context["retrieved_sources"] == [] and context["retrieved_source_ids"] == []
        texts = ["How would you validate missing rows in a sales report?",
            "How would you choose a SQL aggregation for a business metric?",
            "How would you explain uncertainty to a nontechnical audience?",
            "How would you test a transformation before releasing it?",
            "How would you prioritize an ambiguous reporting request?",
            "How would you prevent double counting in joins?",
            "How would you learn an unfamiliar reporting tool?"]
        reason = f"CV: [{context['allowed_cv_evidence_excerpts'][0]}]; Job: [{context['allowed_job_evidence_excerpts'][0]}]. {EVIDENCE_PURPOSE}"
        payload = {"questions": [{"text": t, "target_skill": "analysis", "difficulty": "medium",
                   "reason_for_asking": reason, "reference_criteria": ["The answer should propose a validation workflow."],
                   "source_ids": []} for t in texts]}
        return BytesIO(json.dumps({"model": QWEN, "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(payload)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 20}}).encode())
    class Tracker:
        def __init__(self, *args): pass
        def log(self, **kwargs): return "authored-test-run"
        def request(self, *args, **kwargs): return {}
    class Persisted:
        @classmethod
        def load(cls, *args, **kwargs): return EmptyRetriever()
    monkeypatch.setattr(ablation, "preflight", lambda m: None)
    monkeypatch.setattr(ablation, "TrackingClient", Tracker)
    monkeypatch.setattr(ablation, "load_corpus", lambda p: [None] * 16466)
    monkeypatch.setattr(ablation, "cached_encoder", lambda device: (None, {}))
    monkeypatch.setattr(ablation, "LexicalRetriever", lambda records: EmptyRetriever())
    monkeypatch.setattr(ablation, "BGEFaissRetriever", Persisted)
    monkeypatch.setattr("roleready_ai.model.urlopen", response)
    # CI intentionally has no DVC data bodies. Hash an authored disposable file,
    # rather than accidentally depending on the developer's real corpus cache.
    fixture_corpus = tmp_path / "corpus.jsonl"
    fixture_corpus.write_text('{"purpose":"authored-test-fixture"}\n', encoding="utf-8")
    monkeypatch.setattr(ablation, "CORPUS", fixture_corpus)
    path = tmp_path / "freeze.json"
    hashes = {"ai/data/mission003/processed/corpus.jsonl": "c" * 64,
              "ai/evaluation/ablation/scenarios.json": "e" * 64, "dvc.lock": "d" * 64}
    write_json(path, {"freeze_sha256": "fixture", "execution_code_commit": "fixture", "artifact_hashes": hashes,
        "seed_supported": True, "endpoint": "http://127.0.0.1:11434/v1", "schedule": schedule(scenarios(ASSETS / "scenarios.json")),
        "prompt_sha256": "p", "schema_sha256": "s", "ollama_version": "fixture", "serving_parameters": "fixture"})
    output = tmp_path / "output"
    result = ablation.run(path, output, limit=3)
    assert result["structural_passes"] == 3
    first = {p: p.read_bytes() for p in (output / "cases").glob("*/result.json")}
    assert len(captured) == 3 and len({r["seed"] for r in captured}) == 1
    assert len({r["temperature"] for r in captured}) == 1
    with pytest.raises(FileExistsError):
        ablation.run(path, output, limit=1)
    result = ablation.run(path, output, resume=True, limit=1)
    assert result["completed_sets"] == 4 and len(captured) == 4
    assert all(p.read_bytes() == value for p, value in first.items())


def test_freeze_rejects_modified_or_missing_artifacts(monkeypatch, tmp_path):
    from roleready_ai import experiment_protocol as protocol
    artifact = tmp_path / "input.json"
    artifact.write_text("original")
    from roleready_ai.acquisition import file_sha256
    manifest = {"code_hashes": {}, "artifact_hashes": {"input.json": file_sha256(artifact)}, "schedule": []}
    manifest["freeze_sha256"] = digest(manifest)
    monkeypatch.setattr(protocol, "ROOT", tmp_path)
    monkeypatch.setattr(protocol, "code_hashes", lambda: {})
    monkeypatch.setattr(protocol, "schedule", lambda values: [])
    monkeypatch.setattr(protocol, "scenarios", lambda path: [])
    protocol.verify(manifest)
    artifact.write_text("modified")
    with pytest.raises(ValueError, match="artifact"):
        protocol.verify(manifest)
    manifest["seed_supported"] = True
    with pytest.raises(ValueError, match="checksum"):
        protocol.verify(manifest)


def test_complete_primary_analysis_counts_scenarios_not_questions_or_trials(monkeypatch, tmp_path):
    from roleready_ai import question_review
    mapping = {"freeze_sha256": "test-only", "reviewers": {"1": {}, "2": {}}}
    files = []
    for reviewer in (1, 2):
        rows = []
        for source in scenarios(ASSETS / "scenarios.json"):
            for seed in SETTINGS["seeds"]:
                for condition in CONDITIONS:
                    blind = f"{source['scenario_id']}-{seed}-{condition}"
                    case = {"scenario_id": source["scenario_id"], "seed": seed, "condition": condition, "case_id": blind}
                    mapping["reviewers"][str(reviewer)][blind] = {"case": case, "output_sha256": "authored-fixture"}
                    for number in range(7):
                        rows.append({"reviewer_number": reviewer, "reviewer": f"TEST-REVIEWER-{reviewer}",
                            "blind_id": blind, "question_id": f"q{number}", "dimension": "relevance",
                            "rating": 3 if condition == "none" else 4})
        path = tmp_path / f"test-reviewer-{reviewer}.json"
        write_json(path, {"freeze_sha256": "test-only", "approved": rows})
        files.append(path)
    write_json(tmp_path / "PRIVATE_KEY.json", mapping)
    real_bootstrap = question_review.paired_bootstrap
    monkeypatch.setattr(question_review, "paired_bootstrap", lambda rows: real_bootstrap(rows, repeats=100))
    result = question_review.analyze(tmp_path, files)
    assert result["fully_paired_scenarios"] == 32
    report = result["paired_analysis"]["contrasts"]["bge-faiss-minus-none"]
    assert report["independent_scenarios"] == 32 and report["difference"] == 1
    assert question_review.analyze(tmp_path, files[:1])["paired_analysis"] is None
