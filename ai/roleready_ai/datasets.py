"""Reproducible question-bank preparation; never includes user CVs.

The split hashes the normalized QUESTION, not a source row ID, to ensure that
duplicates across different roles cannot land in both retrieval and held-out data.
Source metadata is recorded, NOT automatically authenticated.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from typing import Iterable, Mapping

QUESTIONS = ("question", "interview_question", "question_text", "text")
ROLES = ("role", "job_role", "category", "position")
ANSWERS = ("reference_answer", "ideal_answer", "answer")
SPLITS = ("train", "validation", "test")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", text, flags=re.UNICODE))


def partition(question: str) -> str:
    """Stable 80/10/10 partition, grouped by normalized question across roles."""
    key = int(sha256(normalize(question).encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if key < 80 else "validation" if key < 90 else "test"


@dataclass(frozen=True)
class QuestionRecord:
    record_id: str
    question: str
    role: str
    source_id: str
    split: str
    reference_answer: str | None = None
    reviewed: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "QuestionRecord":
        return cls(
            record_id=str(payload["record_id"]),
            question=str(payload["question"]),
            role=str(payload["role"]),
            source_id=str(payload["source_id"]),
            split=str(payload["split"]),
            reference_answer=(
                str(payload["reference_answer"])
                if payload.get("reference_answer") is not None else None
            ),
            reviewed=payload.get("reviewed") is True,
        )


def first(row: Mapping[str, object], keys: tuple[str, ...]) -> str:
    return next(
        (str(row[k]).strip() for k in keys if row.get(k) is not None and str(row[k]).strip()),
        "",
    )


def raw_rows(source: Path) -> Iterable[dict[str, object]]:
    if source.suffix.lower() == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                yield row
    elif source.suffix.lower() == ".jsonl":
        with source.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"JSONL line {line_number} must be an object")
                yield value
    else:
        raise ValueError("Only .csv and .jsonl input files are supported.")


def curate(
    rows: Iterable[Mapping[str, object]],
    *,
    source_id: str,
    default_role: str = "general",
    include_roles: set[str] | None = None,
) -> tuple[list[QuestionRecord], dict[str, int]]:
    if not source_id.strip():
        raise ValueError("source_id is required")
    seen: set[tuple[str, str]] = set()
    records: list[QuestionRecord] = []
    counts = {"input": 0, "invalid": 0, "duplicate": 0, "out_of_scope": 0}
    allowed = {normalize(role) for role in include_roles} if include_roles else None
    for row in rows:
        counts["input"] += 1
        question = first(row, QUESTIONS)
        role = first(row, ROLES) or default_role
        if len(question) < 12 or len(question) > 1000 or len(role) > 120:
            counts["invalid"] += 1
            continue
        if allowed is not None and normalize(role) not in allowed:
            counts["out_of_scope"] += 1
            continue
        key = (normalize(question), normalize(role))
        if key in seen:
            counts["duplicate"] += 1
            continue
        seen.add(key)
        answer = first(row, ANSWERS) or None
        record_id = sha256((source_id + "|" + key[1] + "|" + key[0]).encode("utf-8")).hexdigest()[:20]
        records.append(
            QuestionRecord(
                record_id=record_id,
                question=question,
                role=role,
                source_id=source_id,
                split=partition(question),
                reference_answer=answer,
                reviewed=False,  # Raw Q&A is NOT automatically human-reviewed.
            )
        )
    records.sort(key=lambda record: (record.split, record.role.casefold(), record.record_id))
    return records, counts


def write_jsonl(path: Path, records: Iterable[QuestionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path, *, split: str | None = None) -> list[QuestionRecord]:
    result: list[QuestionRecord] = []
    for row in raw_rows(path):
        record = QuestionRecord.from_dict(row)
        if record.split not in SPLITS:
            raise ValueError(f"Unknown split: {record.split}")
        if split is None or record.split == split:
            result.append(record)
    return result


def prepare(
    source: Path,
    output_dir: Path,
    *,
    source_id: str,
    source_url: str,
    license_name: str = "UNVERIFIED",
    include_roles: set[str] | None = None,
) -> dict[str, object]:
    if not source.is_file():
        raise FileNotFoundError(source)
    source_digest = sha256(source.read_bytes()).hexdigest()
    records, counts = curate(raw_rows(source), source_id=source_id, include_roles=include_roles)
    output_dir.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        write_jsonl(output_dir / f"{split}.jsonl", (record for record in records if record.split == split))
    manifest: dict[str, object] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_id": source_id,
        "source_url": source_url,
        "license_declared": license_name,
        "license_verified": False,
        "source_sha256": source_digest,
        "input_filename": source.name,
        "counts": {**counts, "kept": len(records), **{
            split: sum(record.split == split for record in records) for split in SPLITS
        }},
        "warnings": [
            "License and provenance require a manual check before publication or training.",
            "Reference answers and question quality are NOT human-reviewed.",
            "Generated splits are deterministic by normalized question, not role.",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and split a local interview question dataset.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--license", default="UNVERIFIED")
    parser.add_argument("--roles", nargs="*", help="Optional EXACT role labels to include.")
    args = parser.parse_args()
    manifest = prepare(
        args.input, args.out, source_id=args.source_id, source_url=args.source_url,
        license_name=args.license, include_roles=set(args.roles) if args.roles else None,
    )
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
