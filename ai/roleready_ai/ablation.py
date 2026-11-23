"""Controlled three-condition local Qwen experiment. See --help for commands."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time

from .acquisition import file_sha256
from .corpus import load_corpus
from .experiment_protocol import (ASSETS, CORPUS, DIGEST, INDEX, QWEN, ROOT, SETTINGS,
                                  check_serving, freeze, git, now, scenarios, verify)
from .generation import generate_questions
from .indexing import cached_encoder
from .model import OpenAICompatibleQwen
from .qwen_demo import RecordedRetriever, local_api
from .retrieval import BGEFaissRetriever, BGE_REVISION, EmptyRetriever, LexicalRetriever
from .tracking import TrackingClient, digest, read_json, write_json


class RequestJournal:
    """A start record is fsynced before HTTP; response records are never rewritten."""
    def __init__(self, directory: Path):
        self.directory = directory
        self.count = 0
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        event = {**event, "recorded_utc": now()}
        if event["event"] == "request_started":
            self.count += 1
        event["attempt"] = self.count
        path = self.directory / f"attempt-{self.count:02d}-{event['event']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append(event)


def request_metrics(events: list[dict]) -> dict:
    started = [e for e in events if e["event"] == "request_started"]
    finished = [e for e in events if e["event"] == "request_finished"]
    metrics = {"model_requests": len(started), "retries": max(0, len(started) - 1),
               "finished_requests": len(finished), "input_tokens": None, "output_tokens": None,
               "http_latency_ms": sum(e["response"].get("latency_ms", 0) for e in finished)}
    usage = [e["response"].get("usage") for e in finished]
    for output, field in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
        if len(finished) == len(started) and usage and all(isinstance(u, dict) and type(u.get(field)) is int for u in usage):
            metrics[output] = sum(u[field] for u in usage)
    return metrics


def preflight(manifest: dict) -> None:
    verify(manifest)
    origin = manifest["endpoint"][:-3]
    models = local_api(origin, "/api/tags")["models"]
    selected = next((m for m in models if m["name"] == QWEN), None)
    if selected is None or selected["digest"] != DIGEST:
        raise ValueError("Frozen Qwen digest unavailable; never download/substitute")
    if local_api(origin, "/api/version")["version"] != manifest["ollama_version"]:
        raise ValueError("Ollama version changed since freeze")
    show = local_api(origin, "/api/show", {"model": QWEN})
    check_serving(show)
    if show["parameters"] != manifest["serving_parameters"]:
        raise ValueError("Serving parameters changed since freeze")
    if any(m["name"] != QWEN for m in local_api(origin, "/api/ps")["models"]):
        raise ValueError("Other Ollama models loaded; do not change another user's model state")


def log_case(client: TrackingClient, manifest: dict, result: dict, parent: str) -> str:
    return client.log(experiment="roleready-generation", key=manifest["freeze_sha256"] + result["case_id"],
                      parent=parent, params={**result["case"], "freeze_sha256": manifest["freeze_sha256"],
                      "git_commit": manifest["execution_code_commit"], "model_digest": DIGEST,
                      "git_dirty_at_freeze": manifest.get("git_dirty_at_freeze"),
                      "corpus_sha256": manifest["artifact_hashes"]["ai/data/mission003/processed/corpus.jsonl"],
                      "evaluation_sha256": manifest["artifact_hashes"]["ai/evaluation/ablation/scenarios.json"],
                      "dvc_lock_sha256": manifest["artifact_hashes"]["dvc.lock"],
                      "bge_revision": BGE_REVISION, "prompt_sha256": manifest["prompt_sha256"],
                      "schema_sha256": manifest["schema_sha256"], "ollama_version": manifest["ollama_version"],
                      "top_k": 0 if result["case"]["condition"] == "none" else 5,
                      "quantization": "Q4_K_M", "serving_parameters": manifest["serving_parameters"]},
                      metrics={**result["metrics"], "structural_pass": int(result["status"] == "structural_pass")},
                      artifact=result, tags={"evidence_class": "controlled_synthetic", "review_status": "pending",
                                             "inference_status": result["status"]})


def run(manifest_path: Path, output: Path, *, resume: bool = False, tracking_uri: str = "http://127.0.0.1:5000",
        limit: int | None = None) -> dict:
    manifest = read_json(manifest_path)
    preflight(manifest)
    if output.exists() and not resume:
        raise FileExistsError("Use resume; previous experiment records must be preserved")
    output.mkdir(parents=True, exist_ok=True)
    bound = output / "freeze.json"
    if bound.exists() and read_json(bound) != manifest:
        raise ValueError("Output directory belongs to a different frozen experiment")
    if not bound.exists():
        write_json(bound, manifest, exclusive=True)
    # One writer only. A stale lock requires explicit inspection, never blind removal.
    lock = output / "runner.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "started_utc": now()}))
    try:
        client = TrackingClient(tracking_uri)
        parent = client.log(experiment="roleready-generation", key=manifest["freeze_sha256"],
                            params={"condition": "controlled-ablation", "planned_sets": 288,
                                    "execution_code_commit": manifest["execution_code_commit"]},
                            metrics={}, artifact=manifest, tags={"review_status": "pending"}, status="RUNNING")
        records = load_corpus(CORPUS)
        if len(records) != 16466:
            raise ValueError("Expected the verified 16,466-question corpus")
        encoder, embedding = cached_encoder("cpu")
        engines = {"none": EmptyRetriever(), "lexical": LexicalRetriever(records),
                   "bge-faiss": BGEFaissRetriever.load(INDEX, embedding_model=encoder,
                       expected_corpus_sha256=file_sha256(CORPUS), expected_model_revision=BGE_REVISION)}
        inputs = {s["scenario_id"]: s for s in scenarios(ASSETS / "scenarios.json")}
        completed = 0
        for case in manifest["schedule"]:
            directory = output / "cases" / case["case_id"]
            result_path = directory / "result.json"
            if result_path.exists():
                continue
            directory.mkdir(parents=True, exist_ok=True)
            if list(directory.glob("attempt-*-request_started.json")):
                # An interrupted HTTP request has unknown server completion. Preserve
                # it as an interrupted set; do not silently sample another response.
                events = [read_json(p) for p in sorted(directory.glob("attempt-*.json"))]
                interrupted = {"case_id": case["case_id"], "case": case, "status": "interrupted",
                               "metrics": request_metrics(events), "attempts": events,
                               "quality_metrics": None, "review_status": "pending"}
                write_json(result_path, interrupted, exclusive=True)
                continue
            if limit is not None and completed >= limit:
                break
            if completed == 0 or case["ordinal"] % 3 == 0:
                preflight(manifest)
            source = inputs[case["scenario_id"]]
            journal = RequestJournal(directory)
            model = OpenAICompatibleQwen(base_url=manifest["endpoint"], model=QWEN, timeout=600,
                    reasoning_effort="none", max_tokens=4096, seed=case["seed"] if manifest["seed_supported"] else None,
                    top_p=.95, presence_penalty=1.5, request_recorder=journal)
            retriever = RecordedRetriever(engines[case["condition"]])
            result = {"case_id": case["case_id"], "case": case, "started_utc": now(), "status": "error",
                      "quality_metrics": None, "review_status": "pending", "reference_status": "unreviewed",
                      "git_commit_at_execution": git("rev-parse", "HEAD"), "embedding": embedding}
            started = time.perf_counter()
            try:
                generation = generate_questions(model=model, retriever=retriever, cv_text=source["cv_text"],
                    job_description=source["job_description"], role=source["target_role"],
                    experience_level=source["experience_level"], k=0 if case["condition"] == "none" else 5,
                    max_attempts=2)
                if case["condition"] == "none" and (retriever.hits or generation.retrieved_source_ids
                        or any(q.source_ids for q in generation.questions)):
                    raise AssertionError("No-RAG condition contained retrieval grounding")
                result.update(status="structural_pass", generation=asdict(generation))
            except Exception as exc:
                result.update(error_type=type(exc).__name__, error=str(exc))
            result.update(finished_utc=now(), metrics={**request_metrics(journal.events),
                          "pipeline_latency_ms": round((time.perf_counter() - started) * 1000)},
                          retrieved_sources=[h.as_prompt_record() for h in retriever.hits],
                          attempts=journal.events, resolved_schema_sha256=digest(model.response_schema),
                          context_truncation_status="not_independently_verifiable_from_compatible_api")
            for event in journal.events:
                if event["event"] == "request_started":
                    content = event["payload"]["messages"][1]["content"]
                    context = json.loads(content[content.rfind("\n{") + 1:])
                    expected = [h.as_prompt_record() for h in retriever.hits]
                    if context["retrieved_sources"] != expected:
                        raise AssertionError("Prompt lost retrieved texts/IDs")
            write_json(result_path, result, exclusive=True)
            completed += 1
            try:
                run_id = log_case(client, manifest, result, parent)
                write_json(directory / "tracking.json", {"run_id": run_id, "synced_utc": now()})
            except Exception as exc:
                write_json(directory / "tracking-pending.json", {"error_type": type(exc).__name__, "error": str(exc)})
            print(f"{case['ordinal'] + 1}/288 {case['case_id']}: {result['status']}", flush=True)
            summarize(output)
        report = summarize(output)
        if report["completed_sets"] == 288:
            client.request("/api/2.0/mlflow/runs/log-batch", {"run_id": parent, "params": [], "tags": [],
                "metrics": [{"key": k, "value": v, "timestamp": int(time.time() * 1000), "step": 0}
                            for k, v in report.items() if type(v) is int]})
            client.request("/api/2.0/mlflow/runs/update", {"run_id": parent, "status": "FINISHED",
                           "end_time": int(time.time() * 1000)})
        return report
    finally:
        lock.unlink()


def summarize(output: Path) -> dict:
    results = [read_json(p) for p in sorted((output / "cases").glob("*/result.json"))]
    report = {"planned_sets": 288, "completed_sets": len(results),
              "structural_passes": sum(r["status"] == "structural_pass" for r in results),
              "failed_sets": sum(r["status"] != "structural_pass" for r in results),
              "model_requests": sum(r["metrics"].get("model_requests", 0) for r in results),
              "quality_metrics": None, "review_status": "pending", "updated_utc": now()}
    write_json(output / "summary.json", report)
    return report


def sync(output: Path, uri: str) -> dict:
    client = TrackingClient(uri)
    manifest = read_json(output / "freeze.json")
    parent = client.log(experiment="roleready-generation", key=manifest["freeze_sha256"],
                        params={"condition": "controlled-ablation", "planned_sets": 288,
                                "execution_code_commit": manifest["execution_code_commit"]},
                        metrics={}, artifact=manifest, tags={"review_status": "pending"}, status="RUNNING")
    run_ids = []
    for path in sorted((output / "cases").glob("*/result.json")):
        run_id = log_case(client, manifest, read_json(path), parent)
        write_json(path.parent / "tracking.json", {"run_id": run_id, "synced_utc": now()})
        run_ids.append(run_id)
    if summarize(output)["completed_sets"] == 288:
        client.request("/api/2.0/mlflow/runs/update", {"run_id": parent, "status": "FINISHED",
                       "end_time": int(time.time() * 1000)})
    return {"parent_run_id": parent, "case_run_ids": run_ids}


def import_exploratory(output: Path, uri: str) -> dict:
    client = TrackingClient(uri)
    report = read_json(output / "report.json")
    ids = []
    for entry in report["runs"]:
        key = digest({"report_sha256": file_sha256(output / "report.json"),
                      "scenario": entry["scenario_id"], "condition": entry["retrieval"]})
        events = [{"event": "request_started"} for _ in entry["attempt_log"]]
        events += [{"event": "request_finished", "response": a["response"]} for a in entry["attempt_log"]]
        ids.append(client.log(experiment="roleready-generation", key=key,
            params={"condition": entry["retrieval"], "scenario_id": entry["scenario_id"],
                    "model_digest": report["model_digest"], "historical_server_version": report["server_version"],
                    "source_report_sha256": file_sha256(output / "report.json"), "git_commit": "d304d4c4b02b9b56a4f356ef4751b0640ed6da3e"},
            metrics={**request_metrics(events), "pipeline_latency_ms": entry.get("latency_ms"),
                     "structural_pass": int(entry["structural_validation"])},
            artifact={"historical_report": {k: v for k, v in report.items() if k != "runs"},
                      "case": entry, "quality_metrics": None},
            tags={"evidence_class": "exploratory", "review_status": "pending"}))
    retrieval = read_json(ROOT / "ai/evaluation/mission003/retrieval_benchmark.json")
    rid = client.log(experiment="roleready-retrieval", key=digest(retrieval),
        params={"condition": "lexical-vs-bge", "corpus_sha256": retrieval["corpus_sha256"],
                "queries_sha256": retrieval["queries_sha256"], "bge_revision": BGE_REVISION,
                "git_commit": "d304d4c4b02b9b56a4f356ef4751b0640ed6da3e", "top_k": 10,
                "dvc_pointer_sha256": file_sha256(ROOT / "ai/data/mission003/retrieval_runs.dvc")},
        metrics={f"{method}_{k}": v for method, metrics in retrieval["latency_summary"].items() for k, v in metrics.items()},
        artifact=retrieval, tags={"evidence_class": "exploratory", "review_status": "pending"})
    return {"generation_run_ids": ids, "retrieval_run_id": rid}


def probe(output: Path) -> dict:
    """Development-only seed acceptance/warm-up, never a held-out observation."""
    if output.exists():
        raise FileExistsError("Preserve prior development probes")
    output.mkdir(parents=True)
    journal = RequestJournal(output)
    answers = []
    for _ in range(2):
        model = OpenAICompatibleQwen(base_url="http://127.0.0.1:11434/v1", model=QWEN,
            seed=17, max_tokens=32, timeout=600, reasoning_effort="none", request_recorder=journal,
            response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}},
                             "required": ["ok"], "additionalProperties": False})
        answers.append(model.complete_json(system="Return the requested JSON object only.",
            user='Development-only transport test. Return {"ok":true}. No candidate or evaluation input.'))
    metrics = request_metrics(journal.events)
    metrics["retries"] = 0  # These are two independent probe requests, not a retry.
    result = {"purpose": "development_seed_transport_probe_and_warmup", "seed": 17,
              "seed_field_accepted": True, "same_output_observed": answers[0] == answers[1],
              "determinism_claim": False, "metrics": metrics,
              "limitations": "Acceptance does not prove the backend honored every sampler option or deterministic GPU output."}
    write_json(output / "probe.json", result, exclusive=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--unseeded", action="store_true", help="Explicitly document unsupported seeds before freezing")
    f.add_argument("--seed-evidence", type=Path, help="Successful development probe.json, required for seeded freeze")
    p = sub.add_parser("probe")
    p.add_argument("--out", type=Path, required=True)
    for command in ("run", "resume", "sync", "import-exploratory"):
        p = sub.add_parser(command)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--tracking-uri", default="http://127.0.0.1:5000")
        if command in {"run", "resume"}:
            p.add_argument("--manifest", type=Path, required=True)
            p.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(args.out, seed_supported=not args.unseeded, seed_evidence=args.seed_evidence)
        result = {"freeze_sha256": result["freeze_sha256"], "planned_sets": len(result["schedule"])}
    elif args.command == "probe":
        result = probe(args.out)
    elif args.command == "import-exploratory":
        result = import_exploratory(args.out, args.tracking_uri)
    elif args.command == "sync":
        result = sync(args.out, args.tracking_uri)
    else:
        result = run(args.manifest, args.out, resume=args.command == "resume",
                     tracking_uri=args.tracking_uri, limit=args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
