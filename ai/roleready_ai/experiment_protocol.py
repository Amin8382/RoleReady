"""Frozen, hash-bound, local-only experimental protocol and balanced schedule."""
from __future__ import annotations

import itertools
import json
import random
import subprocess
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

from .acquisition import file_sha256
from .generation import SYSTEM_PROMPT, QUESTION_RESPONSE_SCHEMA
from .retrieval import BGE_REVISION
from .tracking import digest, local_url, read_json, write_json

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "ai/evaluation/ablation"
CONDITIONS = ("none", "lexical", "bge-faiss")
ROLES = ("Data Analyst", "Data Scientist", "Data Engineer", "Machine Learning Engineer",
         "AI Engineer", "Backend Developer", "Software Engineer", "MLOps Engineer")
LEVELS = ("entry", "junior", "mid", "senior")
CORPUS = ROOT / "ai/data/mission003/processed/corpus.jsonl"
INDEX = ROOT / "ai/data/mission003/index"
QWEN = "roleready-qwen35-4b:8k"
DIGEST = "27af9727272c8f96be4302b0283fa045132389692e9c86949081d18484d1cfb8"
SETTINGS = {"model": QWEN, "model_digest": DIGEST, "temperature": 0.2, "top_p": 0.95,
            "serving_top_k": 20, "presence_penalty": 1.5, "num_ctx": 8192,
            "max_tokens": 4096, "reasoning_effort": "none", "timeout_seconds": 600,
            "max_attempts": 2, "retrieval_k": 5, "seeds": [17, 29, 43],
            "schedule_seed": 20261122, "bootstrap_seed": 314159, "bootstrap_resamples": 10000,
            "minimum_paired_scenarios": 30}


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
                                   cwd=ROOT, text=True).strip()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scenarios(path: Path) -> list[dict]:
    values = read_json(path)
    if len(values) != 32 or {(s["target_role"], s["experience_level"]) for s in values} != set(itertools.product(ROLES, LEVELS)):
        raise ValueError("Exactly 32 scenarios covering all eight roles and four levels are required")
    if len({s["scenario_id"] for s in values}) != 32:
        raise ValueError("Duplicate scenario ID")
    old = []
    for relative in ("ai/examples/mission002/scenarios.json", "ai/examples/mission003/generation_scenarios.json"):
        old.extend(read_json(ROOT / relative))
    for field in ("cv_text", "job_description"):
        if len({s[field] for s in values}) != 32 or {s[field] for s in values} & {s[field] for s in old}:
            raise ValueError("Evaluation inputs must be distinct from demos and each other")
    if any(s.get("purpose") != "generation_evaluation" or s.get("authorship") != "assistant_synthetic"
           or not s["cv_text"].startswith("Synthetic candidate:") for s in values):
        raise ValueError("Only explicitly synthetic generation-evaluation inputs are supported")
    return values


def schedule(values: list[dict]) -> list[dict]:
    rng = random.Random(SETTINGS["schedule_seed"])
    blocks = [(s["scenario_id"], seed) for s in values for seed in SETTINGS["seeds"]]
    rng.shuffle(blocks)
    orders = list(itertools.permutations(CONDITIONS)) * 16
    rng.shuffle(orders)
    result = []
    for (scenario_id, seed), order in zip(blocks, orders):
        for condition in order:
            result.append({"ordinal": len(result), "scenario_id": scenario_id, "seed": seed,
                           "condition": condition, "case_id": f"{scenario_id}-{seed}-{condition}"})
    return result


def code_hashes() -> dict:
    # Canonical text hashes tolerate checkout line endings, not code changes.
    return {p.relative_to(ROOT).as_posix(): sha256(p.read_text(encoding="utf-8").encode()).hexdigest()
            for p in sorted((ROOT / "ai/roleready_ai").glob("*.py"))}


def freeze(output: Path, *, endpoint: str = "http://127.0.0.1:11434/v1", seed_supported: bool = True,
           seed_evidence: Path | None = None) -> dict:
    from .qwen_demo import local_api
    endpoint = local_url(endpoint)
    if not endpoint.endswith("/v1"):
        raise ValueError("Expected local Ollama /v1 endpoint")
    if git("diff", "HEAD", "--", "ai/roleready_ai"):
        raise ValueError("Commit experiment code before freezing")
    values = scenarios(ASSETS / "scenarios.json")
    evidence = read_json(seed_evidence) if seed_evidence is not None else None
    if seed_supported and (not evidence or evidence.get("seed_field_accepted") is not True):
        raise ValueError("Provide a successful development --seed-evidence probe before seeded freeze")
    paths = [CORPUS, INDEX / "questions.faiss", INDEX / "questions.meta.json", ROOT / "dvc.lock",
             ROOT / "ai/data/mission003/raw.dvc", ROOT / "ai/data/mission003/retrieval_runs.dvc",
             ASSETS / "scenarios.json", ASSETS / "rubric.json", ASSETS / "protocol.json"]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Existing artifact required; no download/rebuild: {path}")
    if file_sha256(CORPUS) != "f4e66cff619dca77d763b9529bcf46df985bf60a02d8ee5c4b65638af34d6cc9":
        raise ValueError("Verified Mission 003 corpus mismatch")
    origin = endpoint[:-3]
    tags = local_api(origin, "/api/tags")["models"]
    model = next((m for m in tags if m["name"] == QWEN), None)
    if model is None or model["digest"] != DIGEST:
        raise ValueError("Existing approved Qwen artifact required; never pull weights")
    show = local_api(origin, "/api/show", {"model": QWEN})
    check_serving(show)
    result = {"schema_version": "ablation-freeze-1.0", "created_utc": now(),
              "execution_code_commit": git("rev-parse", "HEAD"), "code_hashes": code_hashes(),
              "git_dirty_at_freeze": bool(git("diff", "HEAD", "--")), "seed_transport_evidence": evidence,
              "artifact_hashes": {p.relative_to(ROOT).as_posix(): file_sha256(p) for p in paths},
              "dvc_metadata": {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
                               for p in paths if p.name == "dvc.lock" or p.suffix == ".dvc"},
              "settings": SETTINGS, "seed_supported": seed_supported, "endpoint": endpoint,
              "ollama_version": local_api(origin, "/api/version")["version"],
              "serving_parameters": show["parameters"], "model_details": show["details"],
              "bge_revision": BGE_REVISION, "prompt_sha256": digest(SYSTEM_PROMPT),
              "schema_sha256": digest(QUESTION_RESPONSE_SCHEMA), "schedule": schedule(values),
              "review_status": "pending", "quality_metrics": None}
    result["freeze_sha256"] = digest(result)
    write_json(output, result, exclusive=True)
    return result


def check_serving(show: dict) -> None:
    if show["details"].get("quantization_level") != "Q4_K_M" or show["details"].get("family") not in {"qwen35", "qwen3.5"}:
        raise ValueError("Qwen family/quantization mismatch")
    parameters = dict(line.split(None, 1) for line in show["parameters"].splitlines() if line.strip())
    for field, expected in {"temperature": .2, "top_p": .95, "top_k": 20,
                            "presence_penalty": 1.5, "num_ctx": 8192, "num_predict": 4096}.items():
        if float(parameters.get(field, "nan")) != expected:
            raise ValueError(f"Serving setting mismatch: {field}")


def verify(manifest: dict) -> None:
    unsigned = {k: v for k, v in manifest.items() if k != "freeze_sha256"}
    if digest(unsigned) != manifest["freeze_sha256"]:
        raise ValueError("Freeze manifest checksum mismatch")
    if manifest["code_hashes"] != code_hashes():
        raise ValueError("Frozen experiment code has changed")
    for relative, expected in manifest["artifact_hashes"].items():
        if file_sha256(ROOT / relative) != expected:
            raise ValueError(f"Frozen artifact mismatch: {relative}")
    if manifest["schedule"] != schedule(scenarios(ASSETS / "scenarios.json")):
        raise ValueError("Frozen schedule mismatch")
