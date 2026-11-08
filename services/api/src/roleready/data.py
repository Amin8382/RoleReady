"""Immutable downloads, common records and deterministic disjoint splits."""

import csv
import hashlib
import json
import urllib.request
from collections import Counter
from pathlib import Path

from roleready.paths import ROOT, digest, write_json
from roleready.tracking import experiment


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def group_id(question: str) -> str:
    return hashlib.sha256(normalize(question).encode()).hexdigest()


def split_for(question: str) -> str:
    bucket = int(group_id(question)[:8], 16) % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records), encoding="utf-8"
    )


def download_sources(root: Path = ROOT) -> dict:
    manifest_path = root / "configs/datasets.json"
    manifest = json.loads(manifest_path.read_text())
    rows = []
    with experiment("data-download", {"manifest_sha256": digest(manifest_path)}) as run:
        for source in manifest:
            target = root / "data/raw" / source["cache_filename"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or digest(target) != source["sha256"]:
                request = urllib.request.Request(
                    source["source_url"], headers={"User-Agent": "RoleReady/0.1"}
                )
                with urllib.request.urlopen(request, timeout=90) as response:
                    raw = response.read(100 * 1024 * 1024 + 1)
                if len(raw) > 100 * 1024 * 1024:
                    raise ValueError("Source exceeds the download size limit")
                if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                    raise ValueError(f"Checksum mismatch for {source['dataset']}")
                target.write_bytes(raw)
            rows.append(
                {
                    "dataset": source["dataset"],
                    "revision": source["revision"],
                    "sha256": digest(target),
                    "bytes": target.stat().st_size,
                }
            )
        report = {"source_count": len(rows), "sources": rows}
        path = root / "reports/download.json"
        write_json(path, report)
        run.metrics(
            {"sources_verified": len(rows), "bytes_downloaded_or_verified": sum(r["bytes"] for r in rows)}
        )
        run.artifact(path)
    return report


def source_rows(path: Path) -> list[dict]:
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    return read_jsonl(path)


def first(row: dict, *keys: str, default=""):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return value
    return default


def common_record(row: dict, source: dict, index: int) -> dict | None:
    question = str(first(row, "question", "Question", "instruction", "prompt")).strip()
    if not question or len(question) < 10:
        return None
    answer = first(row, "answer", "Answer", "response", "reference_answer", default=None)
    role = str(first(row, "role", "Role", "job_role", "job_title", default="ML Engineer"))
    category = str(
        first(row, "question_category", "category", "Category", "topic", "skill", default="general")
    )
    rid = group_id(question)
    return {
        "id": rid,
        "question": question,
        "reference_answer": answer,
        "role": role,
        "category": category,
        "difficulty": str(first(row, "question_level", "difficulty", "Difficulty", default="unspecified")),
        "keywords": first(row, "keywords", "topic", default=""),
        "source": source["dataset"],
        "source_revision": source["revision"],
        "source_row": index,
        "source_url": source["source_url"],
        "license_metadata": source["publisher_license_metadata"],
        "synthetic": source["dataset"] == "Davichick/InterviewForge_GenDS",
        "human_reviewed": False,
        "split": split_for(question),
        "purpose": source["purpose"],
        "retrieval_allowed": bool(source.get("enabled_for_retrieval")),
        "expected_concepts": row.get("expected_concepts", []),
        "evaluation_rubric": row.get("evaluation_rubric", {}),
        "original_id": row.get("id"),
    }


def prepare_data(root: Path = ROOT) -> dict:
    manifest_path = root / "configs/datasets.json"
    manifest = json.loads(manifest_path.read_text())
    with experiment(
        "data-prepare",
        {"manifest_sha256": digest(manifest_path), "split_rule": "sha256_question_80_10_10_v1"},
    ) as run:
        records, audits = [], []
        for source in manifest:
            path = root / "data/raw" / source["cache_filename"]
            if digest(path) != source["sha256"]:
                raise ValueError(f"Raw source changed: {source['dataset']}")
            rows = source_rows(path)
            unique = {}
            invalid = 0
            for i, row in enumerate(rows):
                record = common_record(row, source, i)
                if record is None:
                    invalid += 1
                elif record["id"] not in unique:
                    unique[record["id"]] = record
            records.extend(unique.values())
            if rows and not unique:
                raise ValueError(f"No usable questions found in {source['dataset']}")
            audits.append(
                {
                    "dataset": source["dataset"],
                    "rows": len(rows),
                    "unique_questions": len(unique),
                    "invalid_rows": invalid,
                    "duplicate_rows": len(rows) - invalid - len(unique),
                    "missing_answers": sum(not r["reference_answer"] for r in unique.values()),
                }
            )
        # Evaluation questions win over the bank if exact duplicates occur across sources.
        evaluation_ids = {r["id"] for r in records if r["purpose"] == "evaluation_only"}
        by_id = {}
        for r in sorted(records, key=lambda x: (x["purpose"] != "evaluation_only", x["source"], x["id"])):
            by_id.setdefault(r["id"], r)
        records = sorted(by_id.values(), key=lambda x: x["id"])
        bank = [
            r
            for r in records
            if r["retrieval_allowed"] and r["split"] == "train" and r["id"] not in evaluation_ids
        ]
        evaluation = [r for r in records if r["purpose"] == "evaluation_only"]
        for split in ["train", "validation", "test"]:
            write_jsonl(
                root / "data/processed" / f"{split}.jsonl",
                [r for r in records if r["split"] == split and r["purpose"] != "evaluation_only"],
            )
        write_jsonl(root / "data/processed/bank.jsonl", bank)
        write_jsonl(root / "data/processed/evaluation.jsonl", evaluation)
        write_jsonl(root / "data/processed/all_records.jsonl", records)
        report = {
            "sources": audits,
            "total_unique_questions": len(records),
            "bank_questions": len(bank),
            "evaluation_questions": len(evaluation),
            "exact_bank_evaluation_overlap": len({r["id"] for r in bank} & evaluation_ids),
            "split_counts": dict(Counter(r["split"] for r in records if r["purpose"] != "evaluation_only")),
            "roles": dict(Counter(r["role"] for r in bank)),
            "bank_sha256": digest(root / "data/processed/bank.jsonl"),
            "limitations": [
                "Structural checks only; no human technical-quality review yet.",
                "Exact duplicates removed; semantic near-duplicate and question-family review remains.",
                "Supplemental ML reference data is excluded from retrieval pending provenance review.",
            ],
        }
        path = root / "reports/data_audit.json"
        write_json(path, report)
        run.metrics(
            {
                "unique_questions": len(records),
                "bank_questions": len(bank),
                "evaluation_questions": len(evaluation),
                "exact_bank_evaluation_overlap": report["exact_bank_evaluation_overlap"],
            }
        )
        run.artifact(path)
    return report
