import json
import math
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from roleready.data import read_jsonl
from roleready.paths import ROOT, digest, write_json
from roleready.tracking import experiment

EMBEDDER = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def record_text(record: dict) -> str:
    return f"{record['role']}. {record['category']}. {record['question']}"


@lru_cache(maxsize=2)
def encoder(revision: str):
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    model = SentenceTransformer(EMBEDDER, revision=revision, trust_remote_code=False, device="cpu")
    model.max_seq_length = 512
    return model


def build_index(root: Path = ROOT) -> dict:
    import faiss

    bank = root / "data/processed/bank.jsonl"
    records = read_jsonl(bank)
    if not records:
        raise ValueError("The retrieval bank is empty")
    config = json.loads((root / "configs/models.json").read_text())
    revision = config[EMBEDDER]["revision"]
    with experiment(
        "bge-index", {"model": EMBEDDER, "revision": revision, "bank_sha256": digest(bank)}
    ) as run:
        vectors = encoder(revision).encode(
            [record_text(r) for r in records],
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        vectors = np.asarray(vectors, dtype=np.float32)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        out = root / "data/index"
        out.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(out / "questions.faiss"))
        metadata = {
            "model": EMBEDDER,
            "revision": revision,
            "dimensions": vectors.shape[1],
            "count": len(records),
            "bank_sha256": digest(bank),
            "max_tokens": 512,
            "query_prefix": QUERY_PREFIX,
            "record_ids": [r["id"] for r in records],
        }
        write_json(out / "metadata.json", metadata)
        summary = {k: v for k, v in metadata.items() if k != "record_ids"}
        write_json(root / "reports/index.json", summary)
        run.metrics({"indexed_questions": len(records), "dimensions": vectors.shape[1]})
        run.artifact(root / "reports/index.json")
    return summary


class Retriever:
    def __init__(self, root: Path = ROOT, backend: str = "bge"):
        self.records = read_jsonl(root / "data/processed/bank.jsonl")
        self.backend = backend
        if backend == "bge":
            import faiss

            self.metadata = json.loads((root / "data/index/metadata.json").read_text())
            if self.metadata["bank_sha256"] != digest(root / "data/processed/bank.jsonl"):
                raise ValueError("The bank changed; rebuild the embedding index")
            if self.metadata["record_ids"] != [r["id"] for r in self.records]:
                raise ValueError("Index row IDs do not match the retrieval bank")
            self.index = faiss.read_index(str(root / "data/index/questions.faiss"))
            if self.index.ntotal != len(self.records) or self.index.d != self.metadata["dimensions"]:
                raise ValueError("Invalid index dimensions or row count")
        elif backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer

            self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=80000)
            self.matrix = self.vectorizer.fit_transform([record_text(r) for r in self.records])
        else:
            raise ValueError("Unknown retrieval backend")

    def search(self, query: str, k: int = 7, role: str | None = None) -> list[dict]:
        if not query.strip() or k < 1:
            return []
        if self.backend == "bge":
            vector = encoder(self.metadata["revision"]).encode(
                [QUERY_PREFIX + query], normalize_embeddings=True
            )
            scores, indices = self.index.search(
                np.asarray(vector, dtype=np.float32), len(self.records) if role else min(k, len(self.records))
            )
            pairs = zip(indices[0].tolist(), scores[0].tolist())
        else:
            scores = (self.matrix @ self.vectorizer.transform([query]).T).toarray().ravel()
            pairs = ((int(i), float(scores[i])) for i in np.argsort(-scores, kind="stable"))
        matches = []
        for i, score in pairs:
            if i < 0:
                continue
            record = self.records[i]
            if role and record["role"] != role:
                continue
            matches.append({**record, "retrieval_score": float(score)})
            if len(matches) >= k:
                break
        return matches


def ranking_metrics(ranked: list[str], relevant: set[str], k: int) -> dict[str, float]:
    top = ranked[:k]
    hits = [i + 1 for i, rid in enumerate(top) if rid in relevant]
    dcg = sum(1 / math.log2(rank + 1) for rank in hits)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return {
        f"hit_rate_at_{k}": float(bool(hits)),
        f"recall_at_{k}": len(hits) / len(relevant) if relevant else 0,
        f"mrr_at_{k}": 1 / hits[0] if hits else 0,
        f"ndcg_at_{k}": dcg / ideal if ideal else 0,
    }


def evaluate_retrieval(root: Path = ROOT) -> dict:
    query_path = root / "data/benchmark/retrieval_queries.json"
    cases = json.loads(query_path.read_text())
    if not cases:
        raise ValueError("Retrieval relevance labels are required")
    summary = {
        "query_count": len(cases),
        "label_status": "assistant-authored exploratory labels; team review pending",
        "models": {},
    }
    for backend in ["tfidf", "bge"]:
        with experiment(
            f"retrieval-{backend}",
            {
                "bank_sha256": digest(root / "data/processed/bank.jsonl"),
                "qrels_sha256": digest(query_path),
                "backend": backend,
                "k": 5,
            },
        ) as run:
            retriever = Retriever(root, backend)
            available = {r["id"] for r in retriever.records}
            per_query = []
            for case in cases:
                relevant = set(case["relevant_ids"])
                if not relevant or not relevant <= available:
                    raise ValueError("Qrels reference missing bank records")
                started = time.perf_counter()
                found = retriever.search(case["query"], 5)
                row = {
                    "id": case["id"],
                    "ranked_ids": [r["id"] for r in found],
                    "latency_seconds": time.perf_counter() - started,
                    **ranking_metrics([r["id"] for r in found], relevant, 5),
                }
                per_query.append(row)
            metrics = {
                key: float(np.mean([r[key] for r in per_query]))
                for key in ["hit_rate_at_5", "recall_at_5", "mrr_at_5", "ndcg_at_5", "latency_seconds"]
            }
            summary["models"][backend] = metrics
            run.metrics(metrics)
            path = root / "reports" / f"retrieval_{backend}.json"
            write_json(
                path, {"metrics": metrics, "cases": per_query, "label_status": summary["label_status"]}
            )
            run.artifact(path)
    write_json(root / "reports/retrieval_comparison.json", summary)
    return summary
