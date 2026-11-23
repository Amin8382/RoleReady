"""Deterministic, provenance-preserving RAG corpus, separate from SFT splits.

Raw source splits are descriptive provenance. They do not decide corpus membership.
Evaluation-only/quarantined sources never become retrieval documents. Answers are
kept in a separate, unreviewed store, never silently supplied as scoring references.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import csv
import json
from pathlib import Path
import re
import unicodedata

from .acquisition import file_sha256, load_registry, snapshot_path, verify_snapshots
from .taxonomy import TAXONOMY_VERSION, canonical_roles

SCHEMA_VERSION = "corpus-1.0"
TRANSFORM_VERSION = "mission003-1.0"
LEVELS = {"Level 1: Foundational": "easy", "Level 2: Practical": "medium", "Level 3: Edge Case & Conflict": "hard"}
TYPES = {
    "Communication & Soft Skills": "behavioral", "Collaboration & Cross-Team Work": "behavioral",
    "Conflict Resolution": "behavioral", "Culture Fit & Values": "behavioral",
    "Motivation & Career Goals": "behavioral", "Salary & Expectations": "behavioral",
    "System Design & Architecture": "system_design", "Scalability & Growth Planning": "system_design",
    "Debugging & Troubleshooting": "debugging", "Incident Response & Ownership": "scenario",
    "Coding & Problem Solving": "problem_solving", "Tools & Frameworks": "technical",
    "Business Impact & Metrics": "analysis", "Prioritization Under Pressure": "scenario",
}


def clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n").strip()
    # Preserve indentation in fenced coding questions; never flatten Python code.
    if "```" in value:
        return "\n".join(line.rstrip() for line in value.splitlines())
    return " ".join(value.split())


def duplicate_key(question: str) -> str:
    cleaned = clean_text(question)
    if "```" in cleaned:
        return cleaned
    # Keep internal punctuation: C++/C, operators and version strings are distinct.
    return cleaned.casefold().rstrip(" .!?")


def stable_id(question: str) -> str:
    return "rrq-" + sha256(duplicate_key(question).encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class CorpusRecord:
    record_id: str
    question: str
    role: str
    roles: tuple[str, ...]
    topic: str | None
    competencies: tuple[str, ...]
    difficulty: str | None
    question_type: str | None
    source_id: str
    source_revision: str
    provenance: tuple[dict, ...]
    schema_version: str = SCHEMA_VERSION
    purpose: str = "retrieval_corpus"
    reviewed: bool = False
    reference_answer: None = None

    @property
    def split(self) -> str:
        """Compatibility marker only; this corpus is not an SFT training split."""
        return "corpus"

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusRecord":
        if value.get("schema_version") != SCHEMA_VERSION or value.get("purpose") != "retrieval_corpus":
            raise ValueError("Only versioned retrieval-corpus documents may be loaded")
        question = value.get("question")
        if not isinstance(question, str) or not 12 <= len(question) <= 6000 or stable_id(question) != value.get("record_id"):
            raise ValueError("Invalid canonical question or stable ID")
        roles = value.get("roles")
        provenance = value.get("provenance")
        if not isinstance(roles, list) or not roles or not all(isinstance(r, str) and canonical_roles(r) for r in roles):
            raise ValueError("Unknown canonical roles")
        if value.get("role") not in roles or not re.fullmatch(r"[0-9a-f]{40}", str(value.get("source_revision", ""))):
            raise ValueError("Invalid canonical source revision or primary role")
        if value.get("topic") is not None and not isinstance(value["topic"], str):
            raise ValueError("Unknown topic must be null, not invented/coerced metadata")
        competencies = value.get("competencies")
        if not isinstance(competencies, list) or not all(isinstance(x, str) and x.strip() for x in competencies):
            raise ValueError("Competencies must be source-derived strings")
        if not isinstance(provenance, list) or not provenance:
            raise ValueError("Source provenance is required")
        for item in provenance:
            if item.get("usage") != "retrieval_corpus" or item.get("license_verified") is not True:
                raise ValueError("Evaluation/quarantined/unapproved source cannot enter retrieval")
            if not re.fullmatch(r"[0-9a-f]{40}", str(item.get("source_revision", ""))) or type(item.get("source_row")) is not int or item["source_row"] <= 0:
                raise ValueError("Invalid occurrence provenance")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("source_file_sha256", ""))):
                raise ValueError("Source artifact checksum is required")
        if not any(p["source_id"] == value["source_id"] and p["source_revision"] == value["source_revision"] for p in provenance):
            raise ValueError("Primary source does not match provenance")
        if value.get("reference_answer") is not None or value.get("reviewed") is not False:
            raise ValueError("Corpus answers/review approvals must remain separate")
        if value.get("difficulty") not in {None, "easy", "medium", "hard"}:
            raise ValueError("Unknown difficulty normalization")
        return cls(**{**value, "roles": tuple(roles), "competencies": tuple(value.get("competencies", [])),
                      "provenance": tuple(provenance)})


def load_corpus(path: Path) -> list[CorpusRecord]:
    records = [CorpusRecord.from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r.record_id for r in records]
    if not records or len(ids) != len(set(ids)):
        raise ValueError("Corpus must be nonempty with unique IDs")
    return records


def source_rows(path: Path):
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("Missing or duplicate CSV headers")
            for number, row in enumerate(reader, 1):
                yield number, row if None not in row else {"_malformed": "csv_field_count"}
    elif path.suffix == ".jsonl":
        with path.open(encoding="utf-8-sig") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    yield number, row if isinstance(row, dict) else {"_malformed": "non_object"}
                except json.JSONDecodeError:
                    yield number, {"_malformed": "invalid_json"}
    else:
        raise ValueError("Only the pinned CSV/JSONL data formats are supported")


def audit_rows(rows: list[tuple[int, dict]]) -> dict:
    columns = sorted({key for _, row in rows for key in row if key != "_malformed"})
    keys = [duplicate_key(row.get("question", "")) for _, row in rows if clean_text(row.get("question"))]
    return {
        "raw_rows": len(rows), "columns": columns,
        "column_types": {key: sorted({type(row.get(key)).__name__ for _, row in rows}) for key in columns},
        "missing_values": {key: sum(row.get(key) in (None, "", []) for _, row in rows) for key in columns},
        "malformed_rows": sum("_malformed" in row for _, row in rows),
        "unique_normalized_questions": len(set(keys)), "duplicate_question_occurrences": len(keys) - len(set(keys)),
    }


def write_rows(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def parse_keywords(value: object) -> tuple[list[str], bool]:
    try:
        if not isinstance(value, str) or len(value) > 10000:
            return [], True
        items = ast.literal_eval(value)
        if not isinstance(items, list) or len(items) > 64 or not all(isinstance(x, str) for x in items):
            return [], True
        return sorted({clean_text(x) for x in items if clean_text(x)}), False
    except (ValueError, SyntaxError, RecursionError):
        return [], True


def prepare_corpus(*, registry_path: Path, raw: Path, output: Path) -> dict:
    registry = load_registry(registry_path)
    verify_snapshots(registry, raw)
    source_data = {}
    for source in sorted(registry["sources"], key=lambda s: s["source_id"]):
        files = [f for f in source["files"] if f["path"].endswith((".csv", ".jsonl"))]
        if len(files) != 1:
            raise ValueError("Exactly one audited data artifact per source is expected")
        source_data[source["source_id"]] = (source, files[0], list(source_rows(snapshot_path(raw, source, files[0]["path"]))))
    reserved = set()
    for source, _, rows in source_data.values():
        if source["usage"] == "evaluation_only":
            for _, row in rows:
                reserved.add(duplicate_key(row.get("question", "")))
                for question in row.get("follow_up_questions", []):
                    if isinstance(question, str):
                        reserved.add(duplicate_key(question))
    merged, rejections, references, source_reports = {}, [], [], []
    for source, data_file, rows in source_data.values():
        counts = Counter({k: 0 for k in ("invalid", "out_of_scope", "excluded_usage", "evaluation_overlap", "exact_duplicate", "retained_unique_primary")})
        flags = Counter()
        for number, row in rows:
            question = clean_text(row.get("question"))
            roles = canonical_roles(clean_text(row.get("role")))
            key = duplicate_key(question)
            reason = None
            if source["usage"] != "retrieval_corpus" or row.get("purpose") in {
                "evaluation_only", "generation_evaluation", "retrieval_evaluation_query", "fine_tuning"}:
                reason = "excluded_usage"
            elif source.get("license_verified") is not True:
                raise ValueError("Retrieval source lacks reviewed license evidence")
            elif "_malformed" in row or not 12 <= len(question) <= 6000 or "\ufffd" in question:
                reason = "invalid"
            elif not roles:
                reason = "out_of_scope"
            elif key in reserved:
                reason = "evaluation_overlap"
            if reason:
                counts[reason] += 1
                rejections.append({"source_id": source["source_id"], "source_revision": source["revision"],
                                   "source_row": number, "reason": reason,
                                   "original_role": row.get("role"), "question_sha256": sha256(question.encode()).hexdigest()})
                continue
            keywords, keyword_error = parse_keywords(row.get("keywords"))
            if keyword_error:
                flags["keywords_parse_error"] += 1
            topic = clean_text(row.get("question_category")) or None
            difficulty = LEVELS.get(row.get("question_level"))
            flags["unknown_difficulty"] += difficulty is None
            occurrence = {
                "source_id": source["source_id"], "source_revision": source["revision"],
                "source_repo": source["repo_id"], "source_url": source["url"],
                "source_file": data_file["path"], "source_row": number,
                "source_file_sha256": data_file["sha256"], "usage": source["usage"],
                "license": source["license"], "license_verified": source["license_verified"],
                "original_role": row.get("role"), "original_difficulty": row.get("question_level"),
                "original_category": row.get("question_category"), "sector": row.get("sector"),
                "interview_stage": row.get("interview_stage"), "authorship": source["authorship"],
                "upstream_split": source.get("upstream_split"), "keyword_parse_error": keyword_error,
            }
            if key in merged:
                counts["exact_duplicate"] += 1
                existing = merged[key]
                existing["roles"] = list(dict.fromkeys([*existing["roles"], *roles]))
                existing["competencies"] = sorted(set(existing["competencies"]) | set(keywords))
                existing["provenance"].append(occurrence)
            else:
                counts["retained_unique_primary"] += 1
                merged[key] = asdict(CorpusRecord(stable_id(question), question, roles[0], roles, topic,
                                                tuple(keywords), difficulty, TYPES.get(topic),
                                                source["source_id"], source["revision"], (occurrence,)))
                # asdict preserves tuples; switch collection fields for predictable JSON validation.
                merged[key]["roles"] = list(roles)
                merged[key]["competencies"] = keywords
                merged[key]["provenance"] = [occurrence]
            answer = clean_text(row.get("reference_answer") or row.get("answer"))
            if answer:
                references.append({"record_id": stable_id(question), "reference_answer": answer,
                                   "reviewed": False, "provenance": occurrence})
        assert sum(counts.values()) == len(rows)
        source_reports.append({**source, "snapshot_audit": audit_rows(rows), "curation": dict(counts), "review_flags": dict(flags)})
    records = sorted(merged.values(), key=lambda r: r["record_id"])
    for record in records:
        CorpusRecord.from_dict(record)
    if not records:
        raise ValueError("No eligible retrieval documents remain")
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "corpus.jsonl", records)
    write_rows(output / "references.unreviewed.jsonl", references)
    write_rows(output / "rejections.jsonl", rejections)
    manifest = {
        "schema_version": SCHEMA_VERSION, "transformation_version": TRANSFORM_VERSION,
        "taxonomy_version": TAXONOMY_VERSION, "purpose": "retrieval_corpus_not_sft_split",
        "source_registry_sha256": file_sha256(registry_path),
        "transformation_code_sha256": {p.name: file_sha256(p) for p in (Path(__file__), Path(__file__).with_name("taxonomy.py"), Path(__file__).with_name("acquisition.py"), Path(__file__).with_name("datasets.py"))},
        "sources": source_reports, "retained_records": len(records),
        "primary_role_counts": dict(sorted(Counter(r["role"] for r in records).items())),
        "applicable_role_counts": dict(sorted(Counter(role for r in records for role in r["roles"]).items())),
        "topic_counts": dict(sorted(Counter(r["topic"] or "unknown" for r in records).items())),
        "unreviewed_reference_answers": len(references), "reserved_evaluation_question_keys": len(reserved),
        "artifacts": {name: {"sha256": file_sha256(output / name), "bytes": (output / name).stat().st_size}
                      for name in ("corpus.jsonl", "references.unreviewed.jsonl", "rejections.jsonl")},
        "limitations": ["Publisher-declared licenses are not an independent audit of every underlying right.",
                        "Source role, difficulty and technical content remain unreviewed.",
                        "Exact normalization deduplication is not semantic deduplication.",
                        "AI/ML Engineer has two explicit normalized role labels; applicable-role counts are not disjoint.",
                        "Source download dates describe the first verified release acquisition, not later replay times."],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_corpus(registry_path=args.registry, raw=args.raw, output=args.out)
    print(json.dumps({"retained_records": manifest["retained_records"],
                      "sources": {s["source_id"]: s["curation"] for s in manifest["sources"]}}, indent=2))


if __name__ == "__main__":
    main()
