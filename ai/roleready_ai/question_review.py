"""Two-person blinded generation review; no model-based rating or approval."""
from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path
import random
import statistics

from .experiment_protocol import ASSETS, SETTINGS, now, scenarios
from .tracking import TrackingClient, digest, read_json, write_json

DIMENSIONS = ("relevance", "personalization", "correctness", "difficulty", "unsupported_assumption")
COMMON = ("relevance", "personalization", "correctness", "difficulty", "diversity", "unsupported_assumption")
FIELDS = ["blind_id", "question_id", "dimension", "cv_text", "job_description", "experience_level",
          "question", "generated_criteria_unreviewed", "source_text", "rating", "status", "rationale", "reviewer", "reviewed_at"]
EDITABLE = {"rating", "status", "rationale", "reviewer", "reviewed_at"}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export(output: Path, destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError("Review exports are immutable; choose a new directory")
    source = {s["scenario_id"]: s for s in scenarios(ASSETS / "scenarios.json")}
    all_records = [read_json(p) for p in sorted((output / "cases").glob("*/result.json"))]
    records = [r for r in all_records if r["status"] == "structural_pass"]
    destination.mkdir(parents=True)
    mapping = {"freeze_sha256": read_json(output / "freeze.json")["freeze_sha256"], "reviewers": {},
               "coverage": {"completed_sets": len(all_records), "successful_sets": len(records),
                            "failed_sets": len(all_records) - len(records), "planned_sets": 288,
                            "uncited_rag_questions": sum(not q["source_ids"] for r in records
                                if r["case"]["condition"] != "none" for q in r["generation"]["questions"])}}
    for number in (1, 2):
        rng = random.Random(20261122 + number)
        ordered = list(records)
        rng.shuffle(ordered)
        core, grounding, keys = [], [], {}
        for index, result in enumerate(ordered):
            blind_id = f"r{number}-{index + 1:04d}"
            case = result["case"]
            scenario = source[case["scenario_id"]]
            keys[blind_id] = {"case": case, "output_sha256": digest(result["generation"])}
            documents = {d["source_id"]: d["question"] for d in result["retrieved_sources"]}
            question_texts = []
            for question in result["generation"]["questions"]:
                text = question["text"]
                question_texts.append(text)
                row = {field: "" for field in FIELDS}
                row.update(blind_id=blind_id, question_id=question["question_id"],
                    cv_text=scenario["cv_text"], job_description=scenario["job_description"],
                    experience_level=scenario["experience_level"], question=text,
                    generated_criteria_unreviewed=json.dumps(question["reference_criteria"], ensure_ascii=False),
                    status="unjudged")
                core.extend([{**row, "dimension": dimension} for dimension in DIMENSIONS])
                if case["condition"] != "none":
                    sources = [documents[s] for s in question["source_ids"]]
                    grounding.append({**row, "dimension": "grounding", "source_text": "\n\n".join(sources),
                                      "status": "unjudged" if sources else "uncited"})
            core.append({**row, "question_id": "__set__", "dimension": "diversity",
                         "question": "\n".join(question_texts), "generated_criteria_unreviewed": ""})
        # Identical blocks are not placed side-by-side, and each evaluator sees a different order.
        directory = destination / f"reviewer-{number}"
        directory.mkdir()
        write_csv(directory / "core.csv", core)
        write_csv(directory / "grounding.csv", grounding)
        mapping["reviewers"][str(number)] = keys
    write_json(destination / "PRIVATE_KEY.json", mapping, exclusive=True)
    write_json(destination / "rubric.json", read_json(ASSETS / "rubric.json"), exclusive=True)
    return {"sets_per_reviewer": len(records), "review_status": "pending",
            "instruction": "Distribute reviewer directories and rubric only. Keep PRIVATE_KEY.json private. Complete core before grounding."}


def import_reviews(directory: Path, completed: Path, *, reviewer_number: int) -> dict:
    """Compare all immutable columns with the original exported sheet."""
    if reviewer_number not in {1, 2}:
        raise ValueError("Expected independent reviewer 1 or 2")
    original = directory / f"reviewer-{reviewer_number}" / completed.name
    if completed.name not in {"core.csv", "grounding.csv"}:
        raise ValueError("Expected core.csv or grounding.csv")
    with original.open(encoding="utf-8-sig", newline="") as stream:
        template = list(csv.DictReader(stream))
    with completed.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    key = lambda row: (row["blind_id"], row["question_id"], row["dimension"])
    expected = {key(r): r for r in template}
    if len(rows) != len(template) or len({key(r) for r in rows}) != len(rows) or set(map(key, rows)) != set(expected):
        raise ValueError("Missing, duplicate or unknown review rows")
    approved = []
    identities = set()
    for row in rows:
        source = expected[key(row)]
        if any(row.get(f) != source[f] for f in FIELDS if f not in EDITABLE):
            raise ValueError("Blinded input or question text was modified")
        if source["status"] == "uncited":
            if row["status"] != "uncited" or row["rating"]:
                raise ValueError("Uncited RAG questions must remain separately uncited")
            continue
        if row["status"] not in {"human_reviewed", "not_assessable"}:
            continue
        if not row["reviewer"].strip() or not row["reviewed_at"].strip():
            raise ValueError("Explicit human reviewer and review date are required")
        from datetime import datetime
        datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
        identities.add(row["reviewer"].strip())
        if row["status"] == "not_assessable":
            if not row["rationale"].strip() or row["rating"]:
                raise ValueError("Not assessable requires rationale and no numeric rating")
            rating = None
        else:
            rating = int(row["rating"])
            if rating not in ({0, 1} if row["dimension"] == "unsupported_assumption" else {1, 2, 3, 4, 5}):
                raise ValueError("Invalid human rating")
            if row["dimension"] == "unsupported_assumption" and rating == 1 and not row["rationale"].strip():
                raise ValueError("Unsupported-assumption flags require offending text/rationale")
        approved.append({**row, "rating": rating, "reviewer_number": reviewer_number})
    if len(identities) > 1:
        raise ValueError("One independent identity per reviewer sheet is required")
    mapping = read_json(directory / "PRIVATE_KEY.json")
    return {"freeze_sha256": mapping["freeze_sha256"], "reviewer_number": reviewer_number,
            "source_sheet": completed.name, "approved": approved, "imported_utc": now(),
            "identity_verification": "declared_human_workflow_not_authenticated"}


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)


def paired_bootstrap(rows: list[dict], *, field: str = "difference", repeats: int = 10000) -> dict:
    rng = random.Random(314159)
    groups = {}
    for row in rows:
        groups.setdefault(row["role"], []).append(row[field])
    samples = []
    for _ in range(repeats):
        drawn = [rng.choice(values) for values in groups.values() for _ in values]
        samples.append(statistics.mean(drawn))
    return {"difference": statistics.mean(r[field] for r in rows),
            "ci95": [percentile(samples, .025), percentile(samples, .975)],
            "ci98_33_bonferroni": [percentile(samples, .05 / 6), percentile(samples, 1 - .05 / 6)],
            "independent_scenarios": len(rows), "resamples": repeats, "method": "paired_role_stratified_scenario_percentile_bootstrap"}


def analyze(directory: Path, review_files: list[Path]) -> dict:
    mapping = read_json(directory / "PRIVATE_KEY.json")
    approved = []
    for path in review_files:
        imported = read_json(path)
        if imported["freeze_sha256"] != mapping["freeze_sha256"]:
            raise ValueError("Review belongs to a different freeze")
        for row in imported["approved"]:
            code = str(row["reviewer_number"])
            bound = mapping["reviewers"][code][row["blind_id"]]
            approved.append({**row, **bound})
    keys = [(r["reviewer_number"], r["blind_id"], r["question_id"], r["dimension"]) for r in approved]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate imported ratings")
    identities = {n: {r["reviewer"].strip().casefold() for r in approved if r["reviewer_number"] == n} for n in (1, 2)}
    if identities[1] & identities[2]:
        raise ValueError("Two distinct independent evaluators are required")
    inputs = {s["scenario_id"]: s for s in scenarios(ASSETS / "scenarios.json")}
    result = {"freeze_sha256": mapping["freeze_sha256"], "review_status": "pending",
              "quality_metrics": None, "paired_analysis": None, "reviewed_rows": len(approved),
              "planned_scenarios": 32, "planned_sets": 288,
              "limitations": ["Synthetic purposive sample; no population representativeness or a priori power claim.",
                  "Quality is conditional on reviewed successful outputs; structural failures must be reported separately.",
                  "Seeds, questions and reviewers are nested measurements, not independent observations."]}
    result["structural_coverage"] = mapping.get("coverage")
    # Only complete 7-question ratings by BOTH reviewers and all three seeds enter
    # primary pairing. No missing-output score is invented.
    paired = []
    for scenario_id, source in inputs.items():
        means = {}
        for condition in ("none", "lexical", "bge-faiss"):
            observed = []
            for seed in SETTINGS["seeds"]:
                for reviewer in (1, 2):
                    rows = [r for r in approved if r["case"]["scenario_id"] == scenario_id
                        and r["case"]["seed"] == seed and r["case"]["condition"] == condition
                        and r["reviewer_number"] == reviewer and r["dimension"] == "relevance"]
                    if len(rows) == 7 and all(r["rating"] is not None for r in rows):
                        observed.append(statistics.mean(r["rating"] for r in rows))
            if len(observed) == 6:
                means[condition] = statistics.mean(observed)
        if len(means) == 3:
            paired.append({"scenario_id": scenario_id, "role": source["target_role"], **means})
    result["fully_paired_scenarios"] = len(paired)
    # Dimension summaries are explicitly approved observations, with denominators.
    if approved:
        summary = {}
        for condition, dimension in itertools.product(("none", "lexical", "bge-faiss"), (*COMMON, "grounding")):
            selected = [r for r in approved if r["case"]["condition"] == condition and r["dimension"] == dimension]
            per_set = {}
            for row in selected:
                if row["rating"] is not None:
                    k = (row["case"]["scenario_id"], row["case"]["seed"], row["reviewer_number"])
                    per_set.setdefault(k, []).append(row["rating"])
            per_scenario = {}
            for (scenario_id, _, _), ratings in per_set.items():
                per_scenario.setdefault(scenario_id, []).append(statistics.mean(ratings))
            values = [statistics.mean(v) for v in per_scenario.values()]
            summary[f"{condition}/{dimension}"] = {"mean": statistics.mean(values) if values else None,
                "ratings": sum(len(v) for v in per_set.values()), "scenarios": len(values),
                "not_assessable": sum(r["rating"] is None for r in selected)}
        result.update(review_status="reviewed_subset_only", quality_metrics=summary)
        matched = {}
        for row in approved:
            if row["rating"] is not None:
                k = (row["case"]["case_id"], row["question_id"], row["dimension"])
                matched.setdefault(k, {})[row["reviewer_number"]] = row["rating"]
        pairs = [p for p in matched.values() if len(p) == 2]
        result["reviewer_agreement"] = {}
        for dimension in (*COMMON, "grounding"):
            pairs = [p for k, p in matched.items() if k[2] == dimension and len(p) == 2]
            result["reviewer_agreement"][dimension] = {"paired_ratings": len(pairs),
                "exact_agreement": statistics.mean(p[1] == p[2] for p in pairs) if pairs else None,
                "mean_absolute_difference": statistics.mean(abs(p[1] - p[2]) for p in pairs) if pairs else None}
    if len(paired) >= 30:
        contrasts = {}
        for left, right in (("lexical", "none"), ("bge-faiss", "none"), ("bge-faiss", "lexical")):
            contrasts[f"{left}-minus-{right}"] = paired_bootstrap(
                [{**row, "difference": row[left] - row[right]} for row in paired])
        result["paired_analysis"] = {"outcome": "human_job_relevance", "contrasts": contrasts}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export")
    p.add_argument("--experiment", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("import")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--reviewer", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("analyze")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--reviews", nargs="*", type=Path, default=[])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tracking-uri", help="Optional local MLflow logging after analysis")
    args = parser.parse_args()
    if args.command == "export":
        result = export(args.experiment, args.out)
    elif args.command == "import":
        result = import_reviews(args.bundle, args.csv, reviewer_number=args.reviewer)
        write_json(args.out, result, exclusive=True)
    else:
        result = analyze(args.bundle, args.reviews)
        write_json(args.out, result, exclusive=True)
        if getattr(args, "tracking_uri", None):
            metrics = {key.replace("/", "_") + "_mean": value["mean"]
                       for key, value in (result["quality_metrics"] or {}).items()}
            result["mlflow_run_id"] = TrackingClient(args.tracking_uri).log(experiment="roleready-generation",
                key=digest(result), params={"condition": "independent-human-review",
                "freeze_sha256": result["freeze_sha256"]}, metrics=metrics,
                artifact=result, tags={"review_status": result["review_status"]})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
