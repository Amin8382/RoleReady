"""Opt-in Qwen demonstration using only the checked-in Mission 002 synthetic data.

Does not pull models, launch services, change global settings or download BGE.
Run from ai/ with a configured local Qwen endpoint and already-cached BGE.
Raw synthetic attempts and GPU samples are saved under gitignored outputs/.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .datasets import load_jsonl
from .generation import QUESTION_RESPONSE_SCHEMA, generate_questions
from .model import OpenAICompatibleQwen
from .retrieval import BGEFaissRetriever, LexicalRetriever, BGE_MODEL, BGE_REVISION

SOURCE_MODEL = "qwen3.5:4b-q4_K_M"
BGE_FILES = ["*.json", "*.txt", "README.md", "model.safetensors", "1_Pooling/*"]


def cached_bge_snapshot():
    from huggingface_hub import snapshot_download

    # Mission 001 intentionally cached only this format, not duplicate ONNX/bin weights.
    return snapshot_download(BGE_MODEL, revision=BGE_REVISION, allow_patterns=BGE_FILES, local_files_only=True)


def local_api(origin: str, path: str, data: dict | None = None) -> dict:
    request = Request(origin + path, data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=240) as response:
        return json.loads(response.read(4_000_000))


def gpu_sample() -> dict:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu",
         "--format=csv,noheader,nounits"], text=True, capture_output=True, timeout=10, check=True,
    )
    used, free, utilization = [int(value.strip()) for value in result.stdout.splitlines()[0].split(",")]
    return {"used_mib": used, "free_mib": free, "utilization_percent": utilization}


def monitored(operation):
    stop = threading.Event()
    samples = []
    started = time.perf_counter()

    def watch():
        while not stop.is_set():
            try:
                samples.append({"elapsed_ms": round((time.perf_counter() - started) * 1000), **gpu_sample()})
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                samples.append({"sampling_error": type(exc).__name__})
            stop.wait(0.5)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        value = operation()
        return value, round((time.perf_counter() - started) * 1000), samples
    finally:
        stop.set()
        thread.join(timeout=11)


class RecordedQwen(OpenAICompatibleQwen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.attempts = []

    def complete_json(self, *, system, user):
        attempt = {"system": system, "user": user}
        try:
            result = super().complete_json(system=system, user=user)
            attempt["status"] = "json_parsed"
            return result
        except Exception as exc:
            attempt.update(status="error", error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            attempt.update(response=self.last_response, raw_content=self.last_content)
            self.attempts.append(attempt)


class RecordedRetriever:
    def __init__(self, engine):
        self.engine = engine
        self.hits = []

    def search(self, **kwargs):
        self.hits = self.engine.search(**kwargs)
        return self.hits


def semantic_screen(encoder, questions) -> dict:
    vectors = encoder.encode([q.text for q in questions], normalize_embeddings=True)
    pairs = sorted(
        [{"left": questions[i].question_id, "right": questions[j].question_id,
          "cosine": round(float(vectors[i] @ vectors[j]), 5)}
         for i in range(len(questions)) for j in range(i + 1, len(questions))],
        key=lambda pair: pair["cosine"], reverse=True,
    )
    return {"threshold": 0.86, "flagged_pairs": [p for p in pairs if p["cosine"] >= 0.86],
            "most_similar_pair": pairs[0],
            "limitation": "Similarity is a review screen, not proof of semantic distinctness. "
                          "CV claims and question relevance require explicit review."}


def run(*, model: str, base_url: str, output: Path, fixtures: Path) -> dict:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("This synthetic demo requires a local HTTP Ollama endpoint")
    if parsed.path.rstrip("/") != "/v1" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use the local Ollama /v1 base URL without credentials or query parameters")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    tags = local_api(origin, "/api/tags")["models"]
    selected = next((item for item in tags if item["name"] == model), None)
    source = next((item for item in tags if item["name"] == SOURCE_MODEL), None)
    if selected is None or source is None:
        raise ValueError("The approved Qwen artifact and served model must already be installed; this command never pulls")
    loaded = local_api(origin, "/api/ps")["models"]
    if any(item["name"] != model for item in loaded):
        raise ValueError("Unload other models before this single-model demonstration")
    show = local_api(origin, "/api/show", {"model": model})
    details = show["details"]
    if details.get("quantization_level") != "Q4_K_M" or details.get("family") not in {"qwen35", "qwen3.5"}:
        raise ValueError("Expected the actual Qwen3.5 Q4_K_M artifact")
    records = load_jsonl(fixtures / "questions.train.jsonl")
    if len(records) != 18 or any(r.split != "train" or r.source_id != "mission002-synthetic" for r in records):
        raise ValueError("Only the 18 checked-in synthetic TRAIN records are permitted")
    scenarios = json.loads((fixtures / "scenarios.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "ollama_version": local_api(origin, "/api/version")["version"],
        "base_url": base_url, "served_model": model, "served_digest": selected["digest"],
        "source_model": SOURCE_MODEL, "source_digest": source["digest"],
        "source_size_bytes": source["size"], "details": details,
        "capabilities": show.get("capabilities"), "thinking": show.get("thinking"),
        "parameters": show.get("parameters"),
        "fixture_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (fixtures / "questions.train.jsonl", fixtures / "scenarios.json")},
        "baseline_gpu": gpu_sample(), "runs": [],
        "quality_status": "Functional demonstration; requires human quality evaluation",
    }

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    print("Starting short real generation", flush=True)
    native, latency, samples = monitored(lambda: local_api(origin, "/api/chat", {
        "model": model, "messages": [{"role": "user", "content": "Explain what a REST API does in one short English sentence."}],
        "stream": False, "think": False, "keep_alive": "30m", "options": {"num_predict": 100, "temperature": 0.2},
    }))
    if native.get("model") != model or not native.get("done") or not native.get("message", {}).get("content", "").strip():
        raise RuntimeError("Short generation did not confirm model identity and actual output")
    report["short_generation"] = {k: native.get(k) for k in (
        "model", "done", "done_reason", "total_duration", "load_duration", "prompt_eval_count",
        "prompt_eval_duration", "eval_count", "eval_duration")}
    report["short_generation"].update(
        text=native["message"]["content"], latency_ms=latency, gpu_samples=samples,
        thinking_characters=len(native["message"].get("thinking", "")),
        loaded_models=local_api(origin, "/api/ps")["models"],
    )
    save()

    from sentence_transformers import SentenceTransformer

    try:
        snapshot = cached_bge_snapshot()
        encoder = SentenceTransformer(snapshot, device="cpu", local_files_only=True)
    except Exception as exc:
        report["setup_error"] = {"type": type(exc).__name__, "message": str(exc)}
        save()
        raise
    engines = {"lexical": LexicalRetriever(records),
               "bge-faiss": BGEFaissRetriever(records, embedding_model=encoder)}
    report["embedding"] = {"model": BGE_MODEL, "revision": BGE_REVISION, "device": "cpu",
                           "reason": "Keep the only large model's GPU measurement separate from BGE allocations"}
    for mode, engine in engines.items():
        for scenario in scenarios:
            print(f"Generating {scenario['scenario_id']} / {mode}", flush=True)
            retriever = RecordedRetriever(engine)
            client = RecordedQwen(base_url=base_url, model=model, response_schema=QUESTION_RESPONSE_SCHEMA,
                                  reasoning_effort="none", timeout=240, max_tokens=4096)
            entry = {"scenario_id": scenario["scenario_id"], "retrieval": mode,
                     "status": "running", "structural_validation": False}
            report["runs"].append(entry)
            save()
            try:
                result, latency, samples = monitored(lambda: generate_questions(
                    model=client, retriever=retriever, cv_text=scenario["cv_text"],
                    job_description=scenario["job_description"], role=scenario["target_role"],
                    experience_level=scenario["experience_level"], k=8, max_attempts=2,
                ))
                screen = semantic_screen(encoder, result.questions)
                entry.update(status="review_required" if screen["flagged_pairs"] else "structural_pass",
                             structural_validation=True, latency_ms=latency, gpu_samples=samples,
                             generation=asdict(result), semantic_screen=screen,
                             quality_review="Manual inspection required for CV claims, relevance and semantic duplication")
            except Exception as exc:
                entry.update(status="error", error_type=type(exc).__name__, error=str(exc))
            finally:
                entry["retrieved_sources"] = [hit.as_prompt_record() for hit in retriever.hits]
                entry["attempt_log"] = client.attempts
                entry["loaded_models"] = local_api(origin, "/api/ps")["models"]
                (output / f"{scenario['scenario_id']}-{mode}.json").write_text(
                    json.dumps(entry, indent=2) + "\n", encoding="utf-8")
                save()
            print(f"Result: {entry['status']}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=SOURCE_MODEL)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--out", type=Path, default=Path("outputs/qwen-mission002"))
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parents[1] / "examples/mission002"
    result = run(model=args.model, base_url=args.base_url, output=args.out, fixtures=fixtures)
    passed = sum(entry["structural_validation"] for entry in result["runs"])
    print(f"Structurally valid runs: {passed}/{len(result['runs'])}")
    if passed != 6:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
