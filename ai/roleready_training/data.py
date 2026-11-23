"""Prepare synthetic personalized SFT drafts; export only two-human-approved targets.

This module neither trains Qwen nor approves a scoring reference answer.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from difflib import SequenceMatcher
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import time

from roleready_ai.ablation import RequestJournal, preflight, request_metrics
from roleready_ai.experiment_protocol import ROOT, LEVELS, QWEN, DIGEST, now, code_hashes, git
from roleready_ai.generation import (generate_questions, validate_questions, validate_evidence,
                                    QUESTION_FIELDS, SYSTEM_PROMPT)
from roleready_ai.model import OpenAICompatibleQwen
from roleready_ai.retrieval import EmptyRetriever
from roleready_ai.tracking import digest, read_json, write_json, TrackingClient
from .recipes import PROJECTS

CHECKS = ("relevance", "personalization", "technical_correctness", "diversity", "difficulty", "no_unsupported_assumptions")
DEFAULT = ROOT / "ai/data/fine_tuning/personalized-v1"


def rows(path: Path) -> list[dict]:
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def write_rows(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def normalized(value: str) -> str:
    return " ".join(value.casefold().split()).rstrip("?.!")


def reserved() -> dict:
    """Read evaluation assets for exclusion only; never use them as teacher input."""
    inputs, questions, sources = [], set(), {}
    for relative in ("ai/examples/mission002/scenarios.json", "ai/examples/mission003/generation_scenarios.json",
                     "ai/evaluation/ablation/scenarios.json"):
        path = ROOT / relative
        values = read_json(path)
        inputs.extend(normalized(v[k]) for v in values for k in ("cv_text", "job_description"))
        sources[relative] = sha256(path.read_bytes()).hexdigest()
    for relative in ("ai/evaluation/mission003/retrieval_queries.jsonl",):
        path = ROOT / relative
        questions.update(normalized(v["query"]) for v in rows(path))
        sources[relative] = sha256(path.read_bytes()).hexdigest()
    # Both accepted and rejected parsed question texts from the frozen experiment
    # are exclusion keys. No evaluation answers become training targets.
    case_paths = sorted((ROOT / "ai/outputs/ablation/run-001/cases").glob("*/result.json"))
    if len(case_paths) != 288:
        raise ValueError("Completed ablation evidence is required to construct the exclusion registry")
    for path in case_paths:
        value = read_json(path)
        questions.update(normalized(q["text"]) for q in value.get("generation", {}).get("questions", []))
        for attempt in value.get("attempts", []):
            content = attempt.get("raw_content")
            if isinstance(content, str):
                try:
                    payload = json.loads(content)
                    questions.update(normalized(q["text"]) for q in payload.get("questions", []) if isinstance(q.get("text"), str))
                except (ValueError, TypeError, AttributeError):
                    pass
        sources[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes()).hexdigest()
    benchmark_paths = list((ROOT / "ai/data/mission003/raw/ml_systems_bench").glob("*/data/questions.jsonl"))
    if len(benchmark_paths) != 1:
        raise ValueError("Verified evaluation-only benchmark snapshot is required for exclusion")
    for path in benchmark_paths:
        for value in rows(path):
            questions.add(normalized(value["question"]))
            questions.update(normalized(x) for x in value.get("follow_up_questions", []) if isinstance(x, str))
        sources[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes()).hexdigest()
    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("text"), str) and "target_skill" in value:
                questions.add(normalized(value["text"]))
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    public_samples = list((ROOT / "ai/examples/mission003").glob("*.json"))
    public_samples.append(ROOT / "ai/evaluation/mission002/synthetic_samples.json")
    for path in public_samples:
        collect(read_json(path))
        sources[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes()).hexdigest()
    return {"input_texts": sorted(set(inputs)), "question_sha256": sorted(digest(q) for q in questions),
            "source_sha256": sources, "usage": "exclusion_only_never_training_input"}


def make_scenarios() -> list[dict]:
    result = []
    responsibilities = {"entry": "a self-directed learning exercise", "junior": "a bounded contributor task",
                        "mid": "a component I maintained", "senior": "a project where I led technical decisions"}
    for role_number, (role, projects) in enumerate(PROJECTS.items(), 1):
        order = list(range(8))
        random.Random(20261123 + role_number).shuffle(order)
        partitions = {p: "train" if n < 6 else "validation" if n == 6 else "test" for n, p in enumerate(order)}
        for p, (project, methods, requirements) in enumerate(projects):
            for level in LEVELS:
                group = f"sft-family-{role_number:02d}-{p:02d}"
                result.append({"record_id": group + "-" + level, "group_id": group,
                    "split": partitions[p], "target_role": role, "experience_level": level,
                    "cv_text": f"Fictional training profile: My project was {project}. It was {responsibilities[level]}. I used {methods}. My documented contribution included explaining the limitations to a teammate.",
                    "job_description": f"We are preparing an English interview for a {level} {role}. The work requires the ability to {requirements}. Explain concrete validation steps, communicate tradeoffs and collaborate on proportionate technical decisions.",
                    "purpose": "personalized_sft_candidate", "authorship": "assistant_authored_synthetic",
                    "license_basis": "newly_authored_fictional_scenarios_no_external_source_text", "review_status": "pending"})
    return result


def check_inputs(values: list[dict], exclusion: dict) -> None:
    if len(values) != 256 or len({v["record_id"] for v in values}) != len(values):
        raise ValueError("Expected 256 unique candidate records")
    groups = {}
    seen = set()
    for value in values:
        if value["purpose"] != "personalized_sft_candidate" or value["authorship"] != "assistant_authored_synthetic":
            raise ValueError("Only newly authored synthetic training candidates are eligible")
        groups.setdefault(value["group_id"], set()).add(value["split"])
        for field in ("cv_text", "job_description"):
            text = normalized(value[field])
            if text in seen or any(text == old or SequenceMatcher(None, text, old).ratio() >= .9 for old in exclusion["input_texts"]):
                raise ValueError("Duplicate or evaluation-overlapping candidate input")
            seen.add(text)
    if any(len(partitions) != 1 for partitions in groups.values()):
        raise ValueError("Project family crosses supervised-learning partitions")


def training_code() -> dict:
    return {p.name: sha256(p.read_text(encoding="utf-8").encode()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))}


def prepare(output: Path) -> dict:
    if output.exists():
        raise FileExistsError("Choose a new dataset version; preserve previous data/reviews")
    exclusion, values = reserved(), make_scenarios()
    check_inputs(values, exclusion)
    manifest = {"version": "personalized-sft-1.0", "created_utc": now(), "records": len(values),
        "code_commit": git("rev-parse", "HEAD"), "prompt_sha256": digest(SYSTEM_PROMPT),
        "teacher_settings": {"temperature": .2, "top_p": .95, "presence_penalty": 1.5,
                             "max_tokens": 4096, "timeout_seconds": 600, "max_attempts": 2,
                             "reasoning_effort": "none", "seed_base": 20261123},
        "split_counts": {s: sum(v["split"] == s for v in values) for s in ("train", "validation", "test")},
        "scenario_sha256": digest(values), "exclusion_sha256": digest(exclusion), "training_code": training_code(),
        "core_code": code_hashes(), "teacher_model": QWEN, "teacher_digest": DIGEST, "retrieval": "none",
        "review_status": "pending", "ready_for_training": False, "human_approved_records": 0,
        "limitations": ["Synthetic pilot, not a proven sufficient training sample.", "Model-generated targets require two human reviews.",
                        "Exact/near input checks and exact target exclusions do not prove absence of all semantic overlap."]}
    output.mkdir(parents=True)
    write_rows(output / "scenarios.jsonl", values)
    write_json(output / "exclusions.json", exclusion, exclusive=True)
    write_json(output / "manifest.json", manifest, exclusive=True)
    return manifest


def verify_dataset(dataset: Path) -> tuple[dict, list[dict], dict]:
    manifest, values, exclusion = read_json(dataset / "manifest.json"), rows(dataset / "scenarios.jsonl"), read_json(dataset / "exclusions.json")
    if digest(values) != manifest["scenario_sha256"] or digest(exclusion) != manifest["exclusion_sha256"]:
        raise ValueError("Dataset/exclusion registry revision mismatch")
    check_inputs(values, exclusion)
    return manifest, values, exclusion


def validate_target(source: dict, target: dict, exclusion: dict) -> None:
    if set(target) != {"questions"} or any(set(q) != QUESTION_FIELDS for q in target["questions"]):
        raise ValueError("Target must match the exact inference output contract")
    questions = validate_questions(target, allowed_source_ids=set(), experience_level=source["experience_level"])
    validate_evidence(questions, cv_text=source["cv_text"], job_description=source["job_description"])
    if any(digest(normalized(q.text)) in exclusion["question_sha256"] for q in questions):
        raise ValueError("Target copies an excluded evaluation question")


def generate(dataset: Path) -> dict:
    manifest, values, exclusion = verify_dataset(dataset)
    if manifest["training_code"] != training_code() or manifest["core_code"] != code_hashes():
        raise ValueError("Teacher/data preparation code changed after preparation")
    preflight(read_json(ROOT / "ai/evaluation/ablation/freeze.json"))
    lock = dataset / "runner.lock"
    with lock.open("x", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "started_utc": now()}, stream)
    try:
        for i, source in enumerate(values):
            directory = dataset / "drafts" / source["record_id"]
            final = directory / "record.json"
            if final.exists():
                continue
            directory.mkdir(parents=True, exist_ok=True)
            if list(directory.glob("attempt-*-request_started.json")):
                write_json(final, {"record_id": source["record_id"], "status": "interrupted",
                                  "target": None, "review_status": "pending"}, exclusive=True)
                continue
            journal = RequestJournal(directory)
            model = OpenAICompatibleQwen(base_url="http://127.0.0.1:11434/v1", model=QWEN, seed=20261123 + i,
                top_p=.95, presence_penalty=1.5, reasoning_effort="none", timeout=600, request_recorder=journal)
            result = {"record_id": source["record_id"], "input_sha256": digest(source), "target": None,
                      "status": "rejected", "review_status": "pending", "started_utc": now()}
            try:
                generated = generate_questions(model=model, retriever=EmptyRetriever(), cv_text=source["cv_text"],
                    job_description=source["job_description"], role=source["target_role"],
                    experience_level=source["experience_level"], k=0, max_attempts=2)
                target = {"questions": [{k: v for k, v in asdict(q).items() if k in QUESTION_FIELDS} for q in generated.questions]}
                result["target"] = target
                validate_target(source, target, exclusion)
                result["status"] = "draft_structural_pass"
            except Exception as exc:
                result.update(error_type=type(exc).__name__, error=str(exc))
            result.update(finished_utc=now(), metrics=request_metrics(journal.events),
                          # Always use the clean initial inference prompt for SFT,
                          # not a retry prompt containing a rejected response's error.
                          messages=journal.events[0]["payload"]["messages"] if journal.events else None)
            write_json(final, result, exclusive=True)
            try:
                run_id = TrackingClient().log(experiment="roleready-sft-data",
                    key=digest({"dataset": manifest["scenario_sha256"], "record": source["record_id"]}),
                    params={"condition": "unreviewed-no-rag-teacher", "record_id": source["record_id"],
                            "split": source["split"], "role": source["target_role"], "level": source["experience_level"],
                            "teacher_digest": DIGEST, "dataset_sha256": manifest["scenario_sha256"]},
                    metrics=result["metrics"], artifact=result,
                    tags={"review_status": "pending", "draft_status": result["status"]})
                write_json(directory / "tracking.json", {"run_id": run_id}, exclusive=True)
            except Exception as exc:
                write_json(directory / "tracking-pending.json", {"error": str(exc)}, exclusive=True)
            report = status(dataset)
            print(f"{i+1}/256 {source['record_id']} {result['status']}", flush=True)
        review_pack(dataset, dataset / "review-pack")
        report = status(dataset)
        try:
            report["mlflow_run_id"] = TrackingClient().log(experiment="roleready-sft-data", key=digest(manifest),
                params={"condition": "no-rag-teacher-drafts", "scenario_sha256": manifest["scenario_sha256"],
                        "teacher_digest": DIGEST, "train": 192, "validation": 32, "test": 32},
                metrics={k: v for k, v in report.items() if type(v) is int}, artifact=report,
                tags={"review_status": "pending", "evidence_class": "synthetic_unreviewed_training_candidates"})
        except Exception as exc:
            report["tracking_error"] = str(exc)
        write_json(dataset / "completion.json", report, exclusive=True)
        return report
    finally:
        lock.unlink()


def status(dataset: Path) -> dict:
    records = [read_json(p) for p in (dataset / "drafts").glob("*/record.json")]
    result = {"planned_records": 256, "completed_records": len(records),
        "structurally_valid_drafts": sum(r["status"] == "draft_structural_pass" for r in records),
        "rejected_or_interrupted": sum(r["status"] != "draft_structural_pass" for r in records),
        "model_requests": sum(r.get("metrics", {}).get("model_requests", 0) for r in records),
        "human_approved_records": 0, "ready_for_training": False, "quality_metrics": None, "review_status": "pending"}
    write_json(dataset / "status.json", result)
    return result


def review_pack(dataset: Path, output: Path) -> dict:
    manifest, values, _ = verify_dataset(dataset)
    if output.exists():
        raise FileExistsError("Preserve prior review packs")
    targets, reviews = [], []
    for source in values:
        path = dataset / "drafts" / source["record_id"] / "record.json"
        draft = read_json(path) if path.exists() else {}
        target = draft.get("target")
        fingerprint = digest({"input": source, "target": target})
        targets.append({"record_id": source["record_id"], "input": source, "target": target,
                        "draft_status": draft.get("status", "not_generated"), "approval_sha256": fingerprint})
        reviews.append({"record_id": source["record_id"], "approval_sha256": fingerprint,
                        "reviewer": None, "reviewed_at": None, "status": "pending",
                        "checks": dict.fromkeys(CHECKS, False), "notes": ""})
    output.mkdir(parents=True)
    write_rows(output / "targets.jsonl", targets)
    for number in (1, 2):
        write_rows(output / f"reviewer-{number}.jsonl", reviews)
    write_json(output / "binding.json", {"scenario_sha256": manifest["scenario_sha256"],
        "instructions": "Humans may correct targets. Both reviewers must approve the recomputed input+target hash, with all checks true. Never approve by copying an agent judgement."}, exclusive=True)
    return {"records": len(targets), "ready_for_training": False}


def clean_messages(source: dict) -> list[dict]:
    captured = []
    class Captured(Exception):
        pass
    class Capture:
        model = "prompt-construction-only-no-inference"
        def complete_json(self, *, system, user):
            captured.extend([{"role": "system", "content": system}, {"role": "user", "content": user}])
            raise Captured()
    try:
        generate_questions(model=Capture(), retriever=EmptyRetriever(), cv_text=source["cv_text"],
            job_description=source["job_description"], role=source["target_role"],
            experience_level=source["experience_level"], k=0)
    except Captured:
        return captured
    raise AssertionError("Prompt capture failed")


def export(dataset: Path, targets_path: Path, reviewer_paths: list[Path], output: Path) -> dict:
    manifest, values, exclusion = verify_dataset(dataset)
    if output.exists():
        raise FileExistsError("Choose a new immutable approved release directory")
    sources = {v["record_id"]: v for v in values}
    targets = rows(targets_path)
    if len(targets) != 256 or {r["record_id"] for r in targets} != set(sources):
        raise ValueError("Complete 256-record reviewed target set required")
    if len(reviewer_paths) != 2:
        raise ValueError("Two independent human review files required")
    reviewers = []
    for path in reviewer_paths:
        data = rows(path)
        if len(data) != 256 or len({r["record_id"] for r in data}) != 256:
            raise ValueError("Missing or duplicate review records")
        reviewers.append({r["record_id"]: r for r in data})
    splits = {s: [] for s in ("train", "validation", "test")}
    target_partitions = {}
    for row in targets:
        source = sources[row["record_id"]]
        if row["input"] != source:
            raise ValueError("Reviewed input differs from the versioned scenario")
        validate_target(source, row["target"], exclusion)
        target_partitions.setdefault(digest(row["target"]), set()).add(source["split"])
        if any(len(s) > 1 for s in target_partitions.values()):
            raise ValueError("Identical complete targets cross supervised-learning partitions")
        fingerprint = digest({"input": source, "target": row["target"]})
        identities = set()
        for reviewer in reviewers:
            approval = reviewer.get(row["record_id"], {})
            if (approval.get("status") != "human_approved" or approval.get("approval_sha256") != fingerprint
                or not approval.get("reviewer") or not approval.get("reviewed_at")
                or not all(approval.get("checks", {}).get(k) is True for k in CHECKS)):
                raise ValueError("Pending, stale or incomplete human approval; training export blocked")
            from datetime import datetime
            datetime.fromisoformat(approval["reviewed_at"].replace("Z", "+00:00"))
            identities.add(approval["reviewer"].strip().casefold())
        if len(identities) != 2 or "" in identities:
            raise ValueError("Two distinct human evaluator identities required")
        splits[source["split"]].append({"record_id": source["record_id"], "group_id": source["group_id"],
            "split": source["split"], "approval_sha256": fingerprint,
            "messages": clean_messages(source) + [{"role": "assistant", "content": json.dumps(row["target"], ensure_ascii=False)}]})
    output.mkdir(parents=True)
    for split, records in splits.items():
        write_rows(output / f"{split}.jsonl", records)
    receipt = {"scenario_sha256": manifest["scenario_sha256"], "ready_for_training": True,
               "teacher_model": manifest["teacher_model"], "teacher_digest": manifest["teacher_digest"],
               "reviewed_targets_sha256": sha256(targets_path.read_bytes()).hexdigest(),
               "counts": {s: len(r) for s, r in splits.items()}, "purpose": "question_generation_not_answer_scoring",
               "review_file_sha256": [sha256(p.read_bytes()).hexdigest() for p in reviewer_paths],
               "files_sha256": {s: sha256((output / f"{s}.jsonl").read_bytes()).hexdigest() for s in splits},
               "identity_verification": "declared_human_workflow_not_authenticated"}
    write_json(output / "manifest.json", receipt, exclusive=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "generate", "status", "review-pack", "export"):
        p = sub.add_parser(command)
        p.add_argument("--dataset", type=Path, default=DEFAULT)
        if command == "review-pack":
            p.add_argument("--out", type=Path, required=True)
        if command == "export":
            p.add_argument("--targets", type=Path, required=True)
            p.add_argument("--reviews", nargs=2, type=Path, required=True)
            p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare": result = prepare(args.dataset)
    elif args.command == "generate": result = generate(args.dataset)
    elif args.command == "status": result = status(args.dataset)
    elif args.command == "review-pack": result = review_pack(args.dataset, args.out)
    else: result = export(args.dataset, args.targets, args.reviews, args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
