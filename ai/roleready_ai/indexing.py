"""Build/reload a persistent exact BGE/FAISS corpus without model downloads."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import sys
from pathlib import Path
import threading
import time

from .acquisition import file_sha256
from .corpus import load_corpus, write_rows
from .retrieval import BGEFaissRetriever, BGE_MODEL, BGE_REVISION, embedding_text

BGE_WEIGHTS_SHA256 = "3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad"


def cached_encoder(device: str):
    started = time.perf_counter()
    from sentence_transformers import SentenceTransformer
    from huggingface_hub import snapshot_download
    import torch
    import_ms = (time.perf_counter() - started) * 1000
    path = snapshot_download(BGE_MODEL, revision=BGE_REVISION, local_files_only=True,
                             allow_patterns=["*.json", "*.txt", "README.md", "model.safetensors", "1_Pooling/*"])
    weights_sha256 = file_sha256(Path(path) / "model.safetensors")
    if weights_sha256 != BGE_WEIGHTS_SHA256:
        raise ValueError("Cached BGE weights differ from the verified revision/hash")
    started = time.perf_counter()
    encoder = SentenceTransformer(path, device=device, local_files_only=True)
    return encoder, {"optional_import_ms": import_ms, "encoder_load_ms": (time.perf_counter() - started) * 1000,
                     "model": BGE_MODEL, "revision": BGE_REVISION, "device": device,
                     "weights_sha256": weights_sha256,
                     "maximum_sequence_tokens": encoder.max_seq_length}


def rss_bytes() -> int:
    """Read local process memory without adding packages to the verified runtime."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        query.restype = wintypes.BOOL
        if not query(kernel.GetCurrentProcess(), ctypes.byref(counters), ctypes.sizeof(counters)):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.WorkingSetSize
    if Path("/proc/self/statm").is_file():
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    raise RuntimeError("Current RSS measurement supports Windows and Linux")


class MemoryMonitor:
    """Sample process RSS, not an exact allocation profiler."""
    def __enter__(self):
        self.start_rss = rss_bytes()
        self.peak_rss = self.start_rss
        self.stop = threading.Event()
        def sample():
            while not self.stop.wait(0.1):
                self.peak_rss = max(self.peak_rss, rss_bytes())
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=2)
        self.final_rss = rss_bytes()
        self.peak_rss = max(self.peak_rss, self.final_rss)


def semantic_candidates(engine: BGEFaissRetriever, *, threshold: float = 0.94, neighbors: int = 6) -> list[dict]:
    if not 0 <= threshold <= 1 or neighbors < 2:
        raise ValueError("Invalid semantic review settings")
    vectors = engine.index.reconstruct_n(0, engine.index.ntotal)
    scores, indices = engine.index.search(vectors, min(neighbors, len(engine.records)))
    pairs = {}
    for left, (row_scores, row_indices) in enumerate(zip(scores, indices)):
        for score, right in zip(row_scores, row_indices):
            if right < 0 or left == right or float(score) < threshold:
                continue
            a, b = sorted((engine.records[left].record_id, engine.records[int(right)].record_id))
            pairs[a, b] = {"left_id": a, "right_id": b, "cosine": round(min(1.0, float(score)), 6),
                            "review_status": "unreviewed_similarity_candidate"}
    return [pairs[key] for key in sorted(pairs)]


def build(*, corpus: Path, output: Path, device: str, report_path: Path | None = None,
          duplicate_threshold: float = 0.94) -> dict:
    # Deterministic local CUDA inference; this is process-local, not a system setting.
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    with MemoryMonitor() as memory:
        records = load_corpus(corpus)
        corpus_digest = file_sha256(corpus)
        encoder, model = cached_encoder(device)
        import faiss
        import numpy as np
        import torch
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        faiss.omp_set_num_threads(min(8, os.cpu_count() or 1))
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        token_counts = []
        for start in range(0, len(records), 256):
            texts = [embedding_text(r) for r in records[start:start+256]]
            token_counts.extend(encoder.tokenizer(texts, truncation=False, return_length=True)["length"])
        engine = BGEFaissRetriever(records, embedding_model=encoder, corpus_sha256=corpus_digest, batch_size=64)
        norms = np.linalg.norm(engine.index.reconstruct_n(0, len(records)), axis=1)
        if engine.index.d != 384 or not np.allclose(norms, 1.0, atol=1e-5):
            raise ValueError("Persisted BGE vectors must be 384-dimensional and L2-normalized")
        started = time.perf_counter()
        engine.save(output)
        save_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        loaded = BGEFaissRetriever.load(output, embedding_model=encoder,
                                        expected_corpus_sha256=corpus_digest, expected_model_revision=BGE_REVISION)
        load_ms = (time.perf_counter() - started) * 1000
        if [asdict(r) for r in loaded.records] != [asdict(r) for r in records]:
            raise ValueError("Reloaded records no longer match the corpus mapping")
        probes = []
        for record in records[::max(1, len(records)//3)][:3]:
            before = engine.search(query=record.question, role=record.role, k=5)
            after = loaded.search(query=record.question, role=record.role, k=5)
            if [h.record.record_id for h in before] != [h.record.record_id for h in after]:
                raise ValueError("Index reload changed search results")
            probes.append({"query_record_id": record.record_id, "returned_ids": [h.record.record_id for h in after],
                           "self_in_top5": record.record_id in {h.record.record_id for h in after}})
        started = time.perf_counter()
        candidates = semantic_candidates(engine, threshold=duplicate_threshold)
        write_rows(output / "semantic_duplicate_candidates.jsonl", candidates)
        duplicate_ms = (time.perf_counter() - started) * 1000
        report = {"embedding": model, "corpus_sha256": corpus_digest, "vectors": engine.index.ntotal,
                  "dimension": engine.index.d, "index_type": "IndexFlatIP", "normalization": "L2",
                  "embedding_text_format": engine.embedding_format,
                  "embedding_text_tokens_max": max(token_counts),
                  "texts_truncated_at_encoder_limit": sum(n > encoder.max_seq_length for n in token_counts),
                  "timings": {**engine.build_timings, "save_ms": save_ms, "load_without_embedding_ms": load_ms,
                              "semantic_candidate_search_ms": duplicate_ms},
                  "index_bytes": (output / "questions.faiss").stat().st_size,
                  "metadata_bytes": (output / "questions.meta.json").stat().st_size,
                  "index_sha256": file_sha256(output / "questions.faiss"),
                  "reload_mapping_verified": True, "reload_probes": probes,
                  "semantic_review": {"threshold": duplicate_threshold, "neighbors_per_document": 6,
                                      "candidate_pairs": len(candidates), "removed": 0,
                                      "limitation": "Top-neighbor candidates only, not exhaustive duplicate labeling or human review"},
                  "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
                  "limitations": ["Times are one local observation, not a statistically reliable benchmark.",
                                  "RSS is sampled and includes model/library/corpus overhead.",
                                  "CUDA allocation excludes other processes and non-PyTorch allocations.",
                                  "Self-query reload probes verify persistence, not retrieval relevance."]}
    report["process_memory"] = {"start_rss_bytes": memory.start_rss, "sampled_peak_rss_bytes": memory.peak_rss,
                                "final_rss_bytes": memory.final_rss}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--duplicate-threshold", type=float, default=0.94)
    args = parser.parse_args()
    result = build(corpus=args.corpus, output=args.out, device=args.device, report_path=args.report,
                   duplicate_threshold=args.duplicate_threshold)
    print(json.dumps({k: result[k] for k in ("vectors", "dimension", "index_bytes", "timings", "semantic_review")}, indent=2))


if __name__ == "__main__":
    main()
