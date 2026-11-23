"""One predeclared synthetic generation evaluation: no RAG, lexical, persisted BGE.

Uses only checked-in Mission 003 scenarios, a pinned corpus/index and an existing
local Qwen service. Does not pull weights or tune prompts against the scenarios.
Raw prompts/results remain under the explicit ignored output directory.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from .acquisition import file_sha256
from .corpus import load_corpus
from .generation import generate_questions, QUESTION_RESPONSE_SCHEMA
from .indexing import cached_encoder
from .qwen_demo import RecordedQwen, RecordedRetriever, local_api, monitored
from .retrieval import BGEFaissRetriever, BGE_REVISION, EmptyRetriever, LexicalRetriever

SCENARIOS = Path(__file__).resolve().parents[1] / "examples/mission003/generation_scenarios.json"


def run(*, corpus: Path, index: Path, output: Path, model: str = "roleready-qwen35-4b:8k",
        base_url: str = "http://127.0.0.1:11434/v1") -> dict:
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
            or parsed.path.rstrip("/") != "/v1" or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("This synthetic evaluation requires the existing local Ollama /v1 endpoint")
    if output.exists():
        raise FileExistsError("Choose a new output directory; evaluation attempts must be preserved")
    origin = parsed.scheme + "://" + parsed.netloc
    selected = next((r for r in local_api(origin, "/api/tags")["models"] if r["name"] == model), None)
    if selected is None:
        raise ValueError("The approved local Qwen profile must already exist; this command never pulls")
    if any(r["name"] != model for r in local_api(origin, "/api/ps")["models"]):
        raise ValueError("Other Ollama models are loaded; use one large model at a time")
    details = local_api(origin, "/api/show", {"model": model})
    if (details["details"]["quantization_level"] != "Q4_K_M"
            or details["details"].get("family") not in {"qwen35", "qwen3.5"}):
        raise ValueError("Expected the verified quantized Qwen profile")
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    if len(scenarios) != 3 or any(s.get("purpose") != "generation_evaluation" or not s["cv_text"].startswith("Synthetic candidate:") for s in scenarios):
        raise ValueError("Only the three checked-in synthetic generation-evaluation cases are permitted")
    records = load_corpus(corpus)
    corpus_digest = file_sha256(corpus)
    encoder, embedding = cached_encoder("cpu")
    engines = {"none": EmptyRetriever(), "lexical": LexicalRetriever(records),
               "bge-faiss": BGEFaissRetriever.load(index, embedding_model=encoder,
                                                  expected_corpus_sha256=corpus_digest,
                                                  expected_model_revision=BGE_REVISION)}
    output.mkdir(parents=True)
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "model": model,
              "model_digest": selected["digest"], "server_version": local_api(origin, "/api/version")["version"],
              "endpoint": base_url + "/chat/completions", "parameters": details.get("parameters"),
              "model_details": details["details"],
              "corpus_sha256": corpus_digest, "scenarios_sha256": file_sha256(SCENARIOS),
              "embedding": embedding, "retrieval_k": 5, "timeout_seconds": 600, "max_attempts": 2,
              "evaluation_policy": "One run of three predeclared scenarios and three modes; no prompt tuning or quality-validation claim.",
              "technical_references": "unreviewed; do not use for scoring", "runs": []}
    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    save()
    for scenario in scenarios:
        for mode, engine in engines.items():
            print(f"Generating {scenario['scenario_id']} / {mode}", flush=True)
            client = RecordedQwen(base_url=base_url, model=model, response_schema=QUESTION_RESPONSE_SCHEMA,
                                  reasoning_effort="none", timeout=600, max_tokens=4096)
            retriever = RecordedRetriever(engine)
            entry = {"scenario_id": scenario["scenario_id"], "retrieval": mode, "structural_validation": False}
            try:
                generated, latency, gpu = monitored(lambda: generate_questions(
                    model=client, retriever=retriever, cv_text=scenario["cv_text"],
                    job_description=scenario["job_description"], role=scenario["target_role"],
                    experience_level=scenario["experience_level"], k=5, max_attempts=2))
                entry.update(status="structural_pass", structural_validation=True,
                             generation=asdict(generated), latency_ms=latency, gpu_samples=gpu)
            except Exception as exc:
                entry.update(status="error", error_type=type(exc).__name__, error=str(exc))
            entry["retrieved_sources"] = [hit.as_prompt_record() for hit in retriever.hits]
            entry["attempt_log"] = client.attempts
            contexts = []
            for attempt in client.attempts:
                user = attempt["user"]
                contexts.append(json.loads(user[user.index("{"):]))
            expected = {hit.record.record_id: hit.record.question for hit in retriever.hits}
            entry["retrieved_text_and_ids_in_every_prompt"] = all(
                {r["source_id"]: r["question"] for r in context["retrieved_sources"]} == expected for context in contexts)
            if not entry["retrieved_text_and_ids_in_every_prompt"]:
                raise AssertionError("Application prompt lost actual retrieved IDs/question text")
            report["runs"].append(entry)
            (output / f"{scenario['scenario_id']}-{mode}.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
            save()
            print(entry["status"], flush=True)
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    report["structural_passes"] = sum(r["structural_validation"] for r in report["runs"])
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(corpus=args.corpus, index=args.index, output=args.out)
    print(f"Structurally valid: {report['structural_passes']}/{len(report['runs'])}")
    if report["structural_passes"] != 9:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
