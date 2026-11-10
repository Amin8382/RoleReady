"""Retrieval rankings, timing and review-gated relevance metrics.

Queries and judgments are separate from corpus documents. Provisional AI labels
never become human ground truth. Recall is relative to assessed relevance pools,
not a claim that every relevant document in a large corpus has been discovered.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import time

from .acquisition import file_sha256
from .corpus import load_corpus
from .indexing import cached_encoder, MemoryMonitor
from .retrieval import BGEFaissRetriever, BGE_REVISION, LexicalRetriever


def load_queries(path: Path) -> list[dict]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = set()
    for query in values:
        if query.get("purpose") != "retrieval_evaluation_query" or not isinstance(query.get("query"), str) or len(query["query"]) < 12:
            raise ValueError("Independent retrieval-evaluation queries are required")
        if not isinstance(query.get("role"), str) or query["query_id"] in ids:
            raise ValueError("Invalid role or duplicate query ID")
        ids.add(query["query_id"])
    if not values:
        raise ValueError("At least one query is required")
    return values


def retrieval_metrics(ranking: list[str], relevance: dict[str, int]) -> dict:
    if len(ranking) != len(set(ranking)):
        raise ValueError("Duplicate ranked IDs would inflate relevance metrics")
    if any(type(grade) is not int or not 0 <= grade <= 3 for grade in relevance.values()):
        raise ValueError("Relevance grades must be integers 0-3")
    positives = {doc for doc, grade in relevance.items() if grade > 0}
    if not positives:
        raise ValueError("Recall/MRR/nDCG require at least one assessed relevant document")
    hits5 = len(set(ranking[:5]) & positives)
    hits10 = len(set(ranking[:10]) & positives)
    reciprocal = next((1 / rank for rank, doc in enumerate(ranking[:10], 1) if doc in positives), 0.0)
    dcg = sum((2 ** relevance.get(doc, 0) - 1) / math.log2(rank + 1)
              for rank, doc in enumerate(ranking[:10], 1))
    ideal = sum((2 ** grade - 1) / math.log2(rank + 1)
                for rank, grade in enumerate(sorted(relevance.values(), reverse=True)[:10], 1))
    return {"precision_at_5": hits5 / 5, "recall_at_5": hits5 / len(positives),
            "recall_at_10": hits10 / len(positives), "mrr_at_10": reciprocal,
            "ndcg_at_10": dcg / ideal}


def reviewed_metrics(rankings: dict, judgments: dict) -> dict:
    for field in ("corpus_sha256", "queries_sha256"):
        if judgments.get(field) != rankings.get(field):
            raise ValueError("Judgment dataset/query revision mismatch")
    labels = {}
    allowed_ids = set(rankings.get("corpus_record_ids", []))
    query_ids = {q["query_id"] for q in rankings["queries"]}
    for judgment in judgments.get("judgments", []):
        key = judgment["query_id"], judgment["record_id"]
        if key[0] not in query_ids or key[1] not in allowed_ids:
            raise ValueError("Judgment points outside the versioned corpus/query set")
        grade = judgment.get("relevance")
        if grade is not None and (type(grade) is not int or not 0 <= grade <= 3):
            raise ValueError("Invalid relevance grade")
        if key in labels:
            raise ValueError("Duplicate relevance judgment")
        labels[key] = judgment
    complete = set(judgments.get("fully_reviewed_query_pools", []))
    if not complete <= query_ids:
        raise ValueError("Unknown reviewed query pool")
    per_query, skipped = [], []
    for query in rankings["queries"]:
        query_id = query["query_id"]
        pool = {hit["source_id"] for method in query["rankings"].values() for hit in method}
        qlabels = {doc: item for (qid, doc), item in labels.items() if qid == query_id}
        human = {doc: item["relevance"] for doc, item in qlabels.items()
                 if item.get("label_status") == "human_reviewed" and item.get("reviewer")
                 and item.get("reviewed_at") and type(item.get("relevance")) is int}
        if query_id not in complete or not pool <= set(human) or not any(g > 0 for g in human.values()):
            skipped.append(query_id)
            continue
        for method, hits in query["rankings"].items():
            per_query.append({"query_id": query_id, "method": method,
                              **retrieval_metrics([h["source_id"] for h in hits], human)})
    aggregate = {}
    for method in {row["method"] for row in per_query}:
        rows = [row for row in per_query if row["method"] == method]
        aggregate[method] = {key: statistics.mean(row[key] for row in rows)
                             for key in rows[0] if key not in {"query_id", "method"}}
    return {"status": "reviewed_subset_only" if per_query else "human_review_required",
            "official_metrics": aggregate or None, "reviewed_query_count": len({r['query_id'] for r in per_query}),
            "query_count": len(rankings["queries"]), "unreviewed_queries": skipped,
            "per_query": per_query,
            "limitations": ["Human-review metadata is a declared approval workflow, not authenticated identity verification.",
                            "Recall/nDCG are relative to assessed pools, which may omit relevant corpus documents.",
                            "MRR is truncated at returned rank 10 and explicitly reported as MRR@10."]}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def import_human_review(pool: dict, csv_path: Path) -> dict:
    """Import explicit approvals only; never infer approval from an AI label."""
    result = json.loads(json.dumps(pool))
    expected = {(j["query_id"], j["record_id"]): j for j in result["judgments"]}
    seen = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = row["query_id"], row["record_id"]
            if key not in expected or key in seen:
                raise ValueError("Unknown or duplicate review-pool pair")
            seen.add(key)
            if row.get("label_status") != "human_reviewed":
                continue
            if not row.get("reviewer", "").strip() or not row.get("reviewed_at", "").strip():
                raise ValueError("Human approval requires explicit reviewer and review date")
            try:
                grade = int(row.get("relevance", ""))
            except ValueError as exc:
                raise ValueError("Approved relevance must be 0-3") from exc
            if not 0 <= grade <= 3:
                raise ValueError("Approved relevance must be 0-3")
            expected[key].update(relevance=grade, label_status="human_reviewed", label_origin="declared_human_review",
                                 reviewer=row["reviewer"].strip(), reviewed_at=row["reviewed_at"].strip(),
                                 rationale=row.get("rationale", ""))
    query_ids = {qid for qid, _ in expected}
    result["fully_reviewed_query_pools"] = sorted(qid for qid in query_ids if all(
        j.get("label_status") == "human_reviewed" for (query_id, _), j in expected.items() if query_id == qid))
    return result


def benchmark(*, corpus: Path, index: Path, queries_path: Path, output: Path,
              report_path: Path | None = None, device: str = "cpu", repeats: int = 3) -> dict:
    if repeats < 1:
        raise ValueError("At least one timing observation is required")
    if (output / "rankings.json").exists():
        raise FileExistsError("Use a new benchmark directory to preserve prior rankings and review work")
    with MemoryMonitor() as memory:
        queries = load_queries(queries_path)
        records = load_corpus(corpus)
        corpus_digest = file_sha256(corpus)
        encoder, model = cached_encoder(device)
        import faiss
        faiss.omp_set_num_threads(8)
        engines = {"lexical": LexicalRetriever(records),
                   "bge-faiss": BGEFaissRetriever.load(index, embedding_model=encoder,
                                                      expected_corpus_sha256=corpus_digest,
                                                      expected_model_revision=BGE_REVISION)}
        document_map = {r.record_id: r for r in records}
        timings = {method: [] for method in engines}
        observed = []
        for query in queries:
            row = {**query, "rankings": {}}
            for method, engine in engines.items():
                runs = []
                for _ in range(repeats):
                    started = time.perf_counter()
                    hits = engine.search(query=query["query"], role=query["role"], k=10)
                    runs.append((time.perf_counter() - started) * 1000)
                if any(hit.record.question != document_map[hit.record.record_id].question for hit in hits):
                    raise ValueError("Retrieved ID/text mapping mismatch")
                row["rankings"][method] = [hit.as_prompt_record() for hit in hits]
                timings[method].append({"query_id": query["query_id"], "role": query["role"],
                                        "latency_ms": runs, "returned": len(hits)})
            observed.append(row)
        rankings = {"schema_version": "retrieval-rankings-1.0", "corpus_sha256": corpus_digest,
                    "queries_sha256": file_sha256(queries_path), "embedding_model": model["model"],
                    "embedding_revision": model["revision"], "depth": 10, "queries": observed}
        rankings["corpus_record_ids"] = sorted(document_map)
        output.mkdir(parents=True, exist_ok=True)
        (output / "rankings.json").write_text(json.dumps(rankings, indent=2) + "\n", encoding="utf-8")
        pool, review_rows = [], []
        for row in observed:
            ids = sorted({h["source_id"] for hits in row["rankings"].values() for h in hits})
            for record_id in ids:
                record = document_map[record_id]
                pool.append({"query_id": row["query_id"], "record_id": record_id, "relevance": None,
                             "label_status": "unjudged", "label_origin": "retriever_pool",
                             "reviewer": None, "reviewed_at": None, "rationale": None})
                review_rows.append({"query_id": row["query_id"], "query": row["query"], "role": row["role"],
                                    "record_id": record_id, "question": record.question,
                                    "source_id": record.source_id, "source_revision": record.source_revision,
                                    "relevance": "", "label_status": "unjudged", "reviewer": "",
                                    "reviewed_at": "", "rationale": ""})
        judgments = {"schema_version": "relevance-judgments-1.0", "corpus_sha256": corpus_digest,
                     "queries_sha256": rankings["queries_sha256"], "fully_reviewed_query_pools": [], "judgments": pool}
        (output / "judgments.unjudged.json").write_text(json.dumps(judgments, indent=2) + "\n", encoding="utf-8")
        with (output / "human_review_pool.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["query_id", "query", "role", "record_id", "question", "source_id",
                                                         "source_revision", "relevance", "label_status", "reviewer", "reviewed_at", "rationale"])
            writer.writeheader()
            writer.writerows(review_rows)
        summary = {
            "corpus_sha256": corpus_digest, "queries_sha256": rankings["queries_sha256"],
            "query_count": len(queries), "roles": sorted({q["role"] for q in queries}),
            "model": model, "repeats_per_query": repeats, "retrieval_depth": 10,
            "timings": timings, "latency_summary": {},
            "label_review": reviewed_metrics(rankings, judgments),
            "query_pool_pairs": len(pool), "human_reviewed_pairs": 0,
            "coverage": {method: {"queries_with_results": sum(row["returned"] > 0 for row in rows),
                                   "queries_with_ten_results": sum(row["returned"] == 10 for row in rows)}
                         for method, rows in timings.items()},
            "limitations": ["No human-reviewed relevance ground truth is available; quality metrics are withheld.",
                            "Nonempty results and valid IDs do not prove semantic relevance.",
                            "Latency includes query encoding/scoring/role filtering but excludes model/index loading.",
                            "The first query may include warm-up effects; repeats are local observations, not a controlled hardware comparison."]}
        for method, rows in timings.items():
            values = [t for row in rows for t in row["latency_ms"]]
            summary["latency_summary"][method] = {"median_ms": statistics.median(values),
                                                 "p95_ms": percentile(values, 0.95), "min_ms": min(values), "max_ms": max(values)}
    summary["sampled_peak_rss_bytes"] = memory.peak_rss
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("benchmark")
    run.add_argument("--corpus", type=Path, required=True)
    run.add_argument("--index", type=Path, required=True)
    run.add_argument("--queries", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--report", type=Path)
    run.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    run.add_argument("--repeats", type=int, default=3)
    metrics = sub.add_parser("metrics")
    metrics.add_argument("--rankings", type=Path, required=True)
    metrics.add_argument("--judgments", type=Path, required=True)
    review = sub.add_parser("import-review")
    review.add_argument("--pool", type=Path, required=True)
    review.add_argument("--csv", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "import-review":
        if args.out.exists():
            raise FileExistsError("Preserve previous human review; choose a new output file")
        result = import_human_review(json.loads(args.pool.read_text(encoding="utf-8")), args.csv)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result = {"fully_reviewed_query_pools": result["fully_reviewed_query_pools"]}
    elif args.command == "metrics":
        result = reviewed_metrics(json.loads(args.rankings.read_text(encoding="utf-8")),
                                  json.loads(args.judgments.read_text(encoding="utf-8")))
    else:
        result = benchmark(corpus=args.corpus, index=args.index, queries_path=args.queries,
                           output=args.out, report_path=args.report, device=args.device, repeats=args.repeats)
        result = {k: result[k] for k in ("query_count", "coverage", "latency_summary", "label_review")}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
