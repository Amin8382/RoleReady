"""Question retrieval: dependency-free lexical baseline and optional real BGE + FAISS.

Explicit corpus documents and legacy TRAIN-split records can be indexed.
Evaluation-only sources and legacy validation/test records cannot be indexed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from functools import lru_cache
import json
from pathlib import Path
import re
import time
from typing import Protocol

from .datasets import QuestionRecord, load_jsonl, normalize
from .corpus import CorpusRecord
from .taxonomy import TAXONOMY_VERSION, search_compatible

RetrievalRecord = QuestionRecord | CorpusRecord

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
    record: RetrievalRecord
    score: float

    def as_prompt_record(self) -> dict[str, object]:
        # Raw reference answers are not supplied to the model without human review.
        result = {
            "source_id": self.record.record_id,
            "question": self.record.question,
            "role": self.record.role,
            "reference_answer": self.record.reference_answer if self.record.reviewed else None,
            "retrieval_score": round(self.score, 5),
        }
        if isinstance(self.record, CorpusRecord):
            result.update(source_dataset=self.record.source_id, source_revision=self.record.source_revision,
                          topic=self.record.topic, difficulty=self.record.difficulty,
                          reviewed=False, purpose=self.record.purpose)
        return result


@lru_cache(maxsize=512)
def compatible_role(candidate_role: str, source_role: str) -> bool:
    """Prefer same role or a general question; avoid drifting to unrelated roles."""
    a, b = normalize(candidate_role), normalize(source_role)
    return b in {"general", a} or (bool(a) and bool(b) and (a in b or b in a)) or search_compatible(candidate_role, source_role)


def indexable(record: RetrievalRecord) -> bool:
    return (isinstance(record, CorpusRecord) and record.purpose == "retrieval_corpus"
            and record.reviewed is False and record.reference_answer is None and bool(record.provenance)
            and all(p.get("usage") == "retrieval_corpus" and p.get("license_verified") is True for p in record.provenance)) or (
                isinstance(record, QuestionRecord) and record.split == "train")


def record_matches_role(role: str, record: RetrievalRecord) -> bool:
    return any(compatible_role(role, r) for r in getattr(record, "roles", (record.role,)))


def embedding_text(record: RetrievalRecord) -> str:
    if isinstance(record, CorpusRecord):
        return (record.question + " | roles: " + ", ".join(record.roles)
                + " | topic: " + (record.topic or "unknown")
                + " | competencies: " + ", ".join(record.competencies)
                + " | difficulty: " + (record.difficulty or "unknown"))
    return record.question + " | " + record.role


def records_fingerprint(records: list[RetrievalRecord]) -> str:
    payload = json.dumps([asdict(r) for r in records], sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha256(payload).hexdigest()


class Retriever(Protocol):
    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]: ...


class EmptyRetriever:
    """Explicit no-retrieval comparison. Never supplies corpus text or citations."""
    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]:
        return []


class LexicalRetriever:
    """Deterministic mockable baseline. Not semantic search or RAG embeddings."""

    def __init__(self, records: list[RetrievalRecord]) -> None:
        if any(not indexable(record) for record in records):
            raise ValueError("Retriever cannot index validation/test/evaluation-only records")
        self.records = list(records)
        self._terms = [tokens(embedding_text(record)) for record in self.records]

    @classmethod
    def from_path(cls, path: Path) -> "LexicalRetriever":
        return cls(load_jsonl(path, split="train"))

    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]:
        if k <= 0:
            return []
        query_terms = tokens(query + " " + role)
        matches = []
        for record, record_terms in zip(self.records, self._terms):
            if not record_matches_role(role, record):
                continue
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
        records: list[RetrievalRecord],
        *,
        model_name: str = BGE_MODEL,
        embedding_model: object | None = None,
        model_revision: str | None = None,
        corpus_sha256: str | None = None,
        batch_size: int = 64,
    ) -> None:
        if not records:
            raise ValueError("At least one corpus or legacy training question is required")
        if any(not indexable(record) for record in records):
            raise ValueError("Retriever cannot index validation/test/evaluation-only records")
        if len({r.record_id for r in records}) != len(records):
            raise ValueError("Duplicate vector-to-question IDs")
        try:
            import faiss
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Install retrieval dependencies: pip install -e '.[retrieval]'") from exc
        if embedding_model is None:
            embedding_model = load_embedding_model(model_name)
        self.records = list(records)
        self.model_name = model_name
        self.model_revision = model_revision or (BGE_REVISION if model_name == BGE_MODEL else "unspecified")
        self.corpus_sha256 = corpus_sha256
        self.embedding_format = "corpus-metadata-v1" if any(isinstance(r, CorpusRecord) for r in records) else "legacy-question-role-v1"
        self.encoder = embedding_model
        self.compute_device = str(getattr(embedding_model, "device", "unspecified"))
        self.faiss = faiss
        self.np = np
        started = time.perf_counter()
        embeddings = np.asarray(
            self.encoder.encode([embedding_text(r) for r in records], normalize_embeddings=True, batch_size=batch_size),
            dtype="float32",
        )
        if embeddings.ndim != 2 or embeddings.shape[0] != len(records):
            raise ValueError("Embedding model produced invalid matrix shape")
        if model_name == BGE_MODEL and embeddings.shape[1] != 384:
            raise ValueError("BGE-small-en-v1.5 must produce 384-dimensional vectors")
        if not np.isfinite(embeddings).all() or (np.linalg.norm(embeddings, axis=1) <= 0).any():
            raise ValueError("Embeddings must be finite and nonzero")
        faiss.normalize_L2(embeddings)
        embedding_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(np.ascontiguousarray(embeddings))
        self.build_timings = {"embedding_ms": embedding_ms, "faiss_build_ms": (time.perf_counter() - started) * 1000}

    def search(self, *, query: str, role: str, k: int = 12) -> list[RetrievedQuestion]:
        if k <= 0:
            return []
        vector = self.np.asarray(
            self.encoder.encode([query + " | " + role], normalize_embeddings=True),
            dtype="float32",
        )
        if vector.shape != (1, self.index.d) or not self.np.isfinite(vector).all() or self.np.linalg.norm(vector) <= 0:
            raise ValueError("Invalid query embedding")
        self.faiss.normalize_L2(vector)
        # Search all for correct role filtering; optimize with per-role indexes later.
        scores, indices = self.index.search(self.np.ascontiguousarray(vector), len(self.records))
        hits = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            record = self.records[int(idx)]
            if record_matches_role(role, record):
                hits.append(RetrievedQuestion(record, float(score)))
                if len(hits) == k:
                    break
        return hits

    def save(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        self.faiss.write_index(self.index, str(destination / "questions.faiss"))
        metadata = {
            "format_version": 2,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "compute_device": self.compute_device,
            "dtype": "float32",
            "corpus_sha256": self.corpus_sha256,
            "embedding_format": self.embedding_format,
            "taxonomy_version": TAXONOMY_VERSION,
            "dimension": self.index.d,
            "index_type": "IndexFlatIP",
            "index_sha256": sha256((destination / "questions.faiss").read_bytes()).hexdigest(),
            "records_sha256": records_fingerprint(self.records),
            "vector_id_sha256": sha256("\n".join(r.record_id for r in self.records).encode()).hexdigest(),
            "metric": "cosine_using_normalized_vectors",
            "records": [asdict(record) for record in self.records],
        }
        (destination / "questions.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, destination: Path, *, embedding_model: object | None = None,
             expected_corpus_sha256: str | None = None,
             expected_model_revision: str | None = None) -> "BGEFaissRetriever":
        # Only read indexes from trusted local sources, never arbitrary uploads.
        metadata = json.loads((destination / "questions.meta.json").read_text(encoding="utf-8"))
        records = [CorpusRecord.from_dict(record) if record.get("purpose") == "retrieval_corpus"
                   else QuestionRecord.from_dict(record) for record in metadata["records"]]
        if not records or any(not indexable(record) for record in records):
            raise ValueError("Invalid index document purposes")
        if len({r.record_id for r in records}) != len(records):
            raise ValueError("Duplicate vector IDs")
        if expected_corpus_sha256 is not None and metadata.get("corpus_sha256") != expected_corpus_sha256:
            raise ValueError("Corpus revision/hash mismatch")
        if expected_model_revision is not None and metadata.get("model_revision") != expected_model_revision:
            raise ValueError("Embedding model revision mismatch")
        if expected_model_revision == BGE_REVISION and metadata.get("model_name") != BGE_MODEL:
            raise ValueError("Embedding model identity mismatch")
        if metadata.get("format_version") == 2:
            if metadata.get("taxonomy_version") != TAXONOMY_VERSION:
                raise ValueError("Role taxonomy revision mismatch")
            if metadata.get("records_sha256") != records_fingerprint(records):
                raise ValueError("Index record metadata checksum mismatch")
            if metadata.get("vector_id_sha256") != sha256("\n".join(r.record_id for r in records).encode()).hexdigest():
                raise ValueError("Vector ID mapping checksum mismatch")
            if metadata.get("index_sha256") != sha256((destination / "questions.faiss").read_bytes()).hexdigest():
                raise ValueError("FAISS index checksum mismatch")
        # Loading must not re-embed the entire corpus. Legacy v1 metadata remains
        # readable, but strict source/model expectations require recorded hashes.
        import faiss
        import numpy as np
        loaded = faiss.read_index(str(destination / "questions.faiss"))
        if loaded.metric_type != faiss.METRIC_INNER_PRODUCT:
            raise ValueError("Expected exact inner-product FAISS index")
        expected_dimension = metadata.get("dimension", 384 if metadata["model_name"] == BGE_MODEL else loaded.d)
        if loaded.ntotal != len(records) or loaded.d != expected_dimension:
            raise ValueError("Index metadata / vector dimensions do not match")
        instance = cls.__new__(cls)
        instance.records = records
        instance.model_name = metadata["model_name"]
        instance.model_revision = metadata.get("model_revision", "legacy-unrecorded")
        instance.compute_device = metadata.get("compute_device", "legacy-unrecorded")
        instance.corpus_sha256 = metadata.get("corpus_sha256")
        instance.embedding_format = metadata.get("embedding_format", "legacy-question-role-v1")
        instance.encoder = embedding_model if embedding_model is not None else load_embedding_model(instance.model_name)
        instance.faiss, instance.np = faiss, np
        instance.build_timings = {}
        instance.index = loaded
        return instance
