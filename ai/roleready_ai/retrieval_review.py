"""Blinded human relevance review and approved-only logging for existing pools."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import random

from .acquisition import file_sha256
from .experiment_protocol import ROOT
from .retrieval_evaluation import import_human_review, reviewed_metrics
from .tracking import TrackingClient, digest, read_json, write_json

POOL = ROOT / "ai/data/mission003/retrieval_runs/run-002"


def export(destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError("Preserve prior human review work")
    with (POOL / "human_review_pool.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows, fields = list(reader), reader.fieldnames
    destination.mkdir(parents=True)
    for number in (1, 2):
        ordered = list(rows)
        random.Random(9000 + number).shuffle(ordered)
        with (destination / f"reviewer-{number}.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(ordered)
    binding = {"pool_sha256": file_sha256(POOL / "judgments.unjudged.json"),
               "rankings_sha256": file_sha256(POOL / "rankings.json"),
               "pairs": len(rows), "review_status": "pending", "official_metrics": None}
    write_json(destination / "binding.json", binding, exclusive=True)
    return binding


def approve(csv_path: Path, output: Path, *, tracking_uri: str) -> dict:
    pool = read_json(POOL / "judgments.unjudged.json")
    # Existing importer validates IDs, grades, reviewer/date and complete pools.
    approved = import_human_review(pool, csv_path)
    metrics = reviewed_metrics(read_json(POOL / "rankings.json"), approved)
    write_json(output, {"judgments": approved, "report": metrics}, exclusive=True)
    numeric = {f"{method}_{key}": value for method, values in (metrics["official_metrics"] or {}).items()
               for key, value in values.items()}
    run_id = TrackingClient(tracking_uri).log(experiment="roleready-retrieval", key=digest(approved),
        params={"condition": "approved-retrieval-review", "corpus_sha256": approved["corpus_sha256"],
                "queries_sha256": approved["queries_sha256"], "review_csv_sha256": file_sha256(csv_path)},
        metrics=numeric, artifact={"judgments": approved, "report": metrics},
        tags={"review_status": metrics["status"]})
    return {"run_id": run_id, "report": metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("import")
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tracking-uri", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    result = export(args.out) if args.command == "export" else approve(args.csv, args.out, tracking_uri=args.tracking_uri)
    import json
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
