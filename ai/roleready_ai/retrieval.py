"""Question retrieval: dependency-free lexical baseline and optional real BGE + FAISS.

Only TRAIN-split records can ever be indexed. Evaluation and validation cases
are not permitted to enter the question bank through this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Protocol

from .datasets import QuestionRecord, load_jsonl, normalize

STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "can", "describe", "do", "explain",
    "for", "from", "have", "how", "in", "is", "it", "of", "on", "or", "our",
    "that", "the", "their", "this", "to", "was", "we", "what", "when", "where",
    "which", "why", "with", "you", "your", "would",
}
BGE_MODEL = "BAAI/bge-small-en-v1.5"
BGE_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"


def load_embedding_model(model_name: str) -> object:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Missing sentence-transformers") from exc
    # Mission 001 cached this immutable revision, not an unversioned main ref.
    kwargs = {"revision": BGE_REVISION} if model_name == BGE_MODEL else {}
    return SentenceTransformer(model_name, **kwargs)


def tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", normalize(text))) - STOPWORDS


@dataclass(frozen=True)
class RetrievedQuestion:
    record: QuestionRecord
    score: float

    def as_prompt_record(self) -> dict[str, object]:
        # Raw reference answers are not supplied to the model without human review.
        return {
            "source_id": self.record.record_id,
            "question": self.record.question,
            "role": self.record.role,
            "reference_answer": self.record.reference_answer if self.record.reviewed else None,
            "retrieval_score": round(self.score, 5),
        }


def compatible_role(candidate_role: str, source_role: str) -> bool:
    """Prefer same role or a general question; avoid drifting to unrelated roles."""
    a, b = normalize(candidate_role), normalize(source_role)
    return b in {"general", a} or (bool(a) and bool(b) and (a in b or b in a))


class Retriever(Protocol):
    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]: ...


class LexicalRetriever:
    """Deterministic mockable baseline. Not semantic search or RAG embeddings."""

    def __init__(self, records: list[QuestionRecord]) -> None:
        if any(record.split != "train" for record in records):
            raise ValueError("Retriever cannot index validation/test records")
        self.records = list(records)

    @classmethod
    def from_path(cls, path: Path) -> "LexicalRetriever":
        return cls(load_jsonl(path, split="train"))

    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]:
        if k <= 0:
            return []
        query_terms = tokens(query + " " + role)
        matches = []
        for record in self.records:
            if not compatible_role(role, record.role):
                continue
            record_terms = tokens(record.question + " " + record.role)
            overlap = len(query_terms & record_terms)
            denominator = max(1, len(query_terms | record_terms))
            score = overlap / denominator
            if normalize(record.role) == normalize(role):
                score += 0.1
            matches.append(RetrievedQuestion(record, score))
        return sorted(matches, key=lambda hit: (-hit.score, hit.record.record_id))[:k]


class BGEFaissRetriever:
    """Real BGE-small-en-v1.5 embeddings with normalized FAISS inner-product search.

    Install with: pip install -e '.[retrieval]'
    Loading the embedding model may download weights from Hugging Face on first use.
    """

    def __init__(
        self,
        records: list[QuestionRecord],
        *,
        model_name: str = BGE_MODEL,
        embedding_model: object | None = None,
    ) -> None:
        if not records:
            raise ValueError("At least one training question is required")
        if any(record.split != "train" for record in records):
            raise ValueError("Retriever cannot index validation/test records")
        try:
            import faiss
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Install retrieval dependencies: pip install -e '.[retrieval]'") from exc
        if embedding_model is None:
            embedding_model = load_embedding_model(model_name)
        self.records = list(records)
        self.model_name = model_name
        self.encoder = embedding_model
        self.faiss = faiss
        self.np = np
        embeddings = np.asarray(
            self.encoder.encode([r.question + " | " + r.role for r in records], normalize_embeddings=True),
            dtype="float32",
        )
        if embeddings.ndim != 2 or embeddings.shape[0] != len(records):
            raise ValueError("Embedding model produced invalid matrix shape")
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(np.ascontiguousarray(embeddings))

    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]:
        if k <= 0:
            return []
        vector = self.np.asarray(
            self.encoder.encode([query + " | " + role], normalize_embeddings=True),
            dtype="float32",
        )
        # Search all for correct role filtering; optimize with per-role indexes later.
        scores, indices = self.index.search(self.np.ascontiguousarray(vector), len(self.records))
        hits = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            record = self.records[int(idx)]
            if compatible_role(role, record.role):
                hits.append(RetrievedQuestion(record, float(score)))
                if len(hits) == k:
                    break
        return hits

    def save(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        self.faiss.write_index(self.index, str(destination / "questions.faiss"))
        metadata = {
            "model_name": self.model_name,
            "metric": "cosine_using_normalized_vectors",
            "records": [asdict(record) for record in self.records],
        }
        (destination / "questions.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, destination: Path, *, embedding_model: object | None = None) -> "BGEFaissRetriever":
        # Only read indexes from trusted local sources, never arbitrary uploads.
        metadata = json.loads((destination / "questions.meta.json").read_text(encoding="utf-8"))
        records = [QuestionRecord.from_dict(record) for record in metadata["records"]]
        instance = cls(records, model_name=metadata["model_name"], embedding_model=embedding_model)
        loaded = instance.faiss.read_index(str(destination / "questions.faiss"))
        if loaded.ntotal != len(records) or loaded.d != instance.index.d:
            raise ValueError("Index metadata / vector dimensions do not match")
        instance.index = loaded
        return instance
