"""Opt-in, synthetic BGE/voice inference with separate download/load timings.

This CLI downloads only the selected small model. It never serves or downloads
Qwen/Prometheus. Reports/audio belong in the gitignored outputs directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time
from typing import Any, Callable

SYNTHETIC_QUESTION = "Tell me about an engineering project you built."
MODEL_IDS = {
    "bge": "BAAI/bge-small-en-v1.5",
    "whisper": "Systran/faster-whisper-small.en",
    "kokoro": "hexgrad/Kokoro-82M",
}


def gpu_memory() -> dict[str, Any]:
    """Snapshots are whole-device use; torch peaks exclude CTranslate2 allocations."""
    import torch

    result: dict[str, Any] = {}
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        result.update(
            torch_allocated_mib=round(torch.cuda.memory_allocated() / 2**20, 2),
            torch_reserved_mib=round(torch.cuda.memory_reserved() / 2**20, 2),
            torch_peak_allocated_mib=round(torch.cuda.max_memory_allocated() / 2**20, 2),
        )
    try:
        query = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        result["nvidia_smi_name_total_used_free_mib"] = query.stdout.strip().splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        result["nvidia_smi_error"] = type(exc).__name__
    return result


def benchmark(
    name: str, *, device: str, report_path: Path, audio: Path,
    output: Path, revision: str = "main",
) -> dict[str, Any]:
    import torch

    report: dict[str, Any] = {
        "model_id": MODEL_IDS[name], "device": device, "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "torch": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "timings_ms": {}, "gpu_memory": {},
        "packages": {},
        "limitations": "Synthetic smoke only; no quality, accent or integration validation. "
                        "GPU snapshots include desktop/other processes; torch peaks exclude CTranslate2.",
    }
    for package in ("sentence-transformers", "faiss-cpu", "numpy", "transformers",
                    "kokoro", "faster-whisper", "ctranslate2", "soundfile"):
        try:
            report["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass

    def save() -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def measure(phase: str, operation: Callable[[], Any]) -> Any:
        print(f"Starting {phase}", flush=True)
        report["phase"] = phase
        save()
        started = time.perf_counter()
        try:
            return operation()
        finally:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            report["timings_ms"][phase] = round((time.perf_counter() - started) * 1000, 2)
            report["gpu_memory"][phase] = gpu_memory()
            save()

    try:
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is False")
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        report["gpu_memory"]["baseline"] = gpu_memory()

        def download() -> Path:
            from huggingface_hub import HfApi, snapshot_download

            resolved = HfApi().model_info(MODEL_IDS[name], revision=revision).sha
            report["revision"] = resolved
            patterns = {
                "bge": ["*.json", "*.txt", "README.md", "model.safetensors", "1_Pooling/*"],
                "whisper": ["*.json", "*.txt", "model.bin"],
                "kokoro": ["config.json", "kokoro-v1_0.pth", "voices/af_heart.pt"],
            }
            return Path(snapshot_download(
                MODEL_IDS[name], revision=resolved, allow_patterns=patterns[name],
            ))

        snapshot = measure("artifact_prepare", download)
        if name == "bge":
            from sentence_transformers import SentenceTransformer
            from .datasets import QuestionRecord
            from .retrieval import BGEFaissRetriever

            encoder = measure("model_load", lambda: SentenceTransformer(
                str(snapshot), device=device, local_files_only=True,
            ))
            records = [
                QuestionRecord("sql", "How do you optimize SQL queries and indexes?",
                               "Data Engineer", "synthetic", "train"),
                QuestionRecord("team", "How do you resolve disagreements in a team?",
                               "general", "synthetic", "train"),
                QuestionRecord("ui", "How do you build a React user interface?",
                               "Frontend Engineer", "synthetic", "train"),
            ]
            engine = measure("embed_and_index", lambda: BGEFaissRetriever(
                records, model_name=MODEL_IDS[name], embedding_model=encoder,
            ))
            hits = measure("inference", lambda: engine.search(
                query="SQL query performance optimization with indexes", role="Data Engineer", k=3,
            ))
            if [hit.record.record_id for hit in hits] != ["sql", "team"]:
                raise RuntimeError("Expected SQL first, general question second and no frontend question")
            report["result"] = {
                "index_vectors": engine.index.ntotal, "dimensions": engine.index.d,
                "faiss_device": "cpu", "embedding_device": str(encoder.device),
                "hits": [{"id": hit.record.record_id, "score": hit.score} for hit in hits],
            }
        elif name == "kokoro":
            from kokoro import KModel, KPipeline
            from .voice import synthesize_question

            def load_kokoro() -> Any:
                model = KModel(
                    repo_id=MODEL_IDS[name], config=str(snapshot / "config.json"),
                    model=str(snapshot / "kokoro-v1_0.pth"),
                ).to(device).eval()
                pipeline = KPipeline(lang_code="a", repo_id=MODEL_IDS[name], model=model)
                pipeline.voices["af_heart"] = torch.load(
                    snapshot / "voices/af_heart.pt", map_location="cpu", weights_only=True,
                )
                return pipeline

            pipeline = measure("model_load", load_kokoro)
            measure("inference", lambda: synthesize_question(
                SYNTHETIC_QUESTION, output, pipeline=pipeline,
            ))
            import numpy as np
            import soundfile as sf

            samples, rate = sf.read(output)
            if rate != 24000 or samples.size == 0 or not np.isfinite(samples).all() or not np.any(samples):
                raise RuntimeError("Kokoro must produce finite, non-silent 24 kHz audio")
            report["result"] = {
                "text": SYNTHETIC_QUESTION, "output": str(output), "voice": "af_heart",
                "sample_rate": rate, "duration_seconds": round(len(samples) / rate, 3),
                "peak_amplitude": float(np.abs(samples).max()),
            }
        else:
            from faster_whisper import WhisperModel
            from .voice import transcribe_english

            compute_type = "float16" if device == "cuda" else "int8"
            report["compute_type"] = compute_type
            model = measure("model_load", lambda: WhisperModel(
                str(snapshot), device=device, compute_type=compute_type,
            ))
            result = measure("inference", lambda: transcribe_english(audio, model=model))
            report["result"] = {"transcript": result.text, "language": result.language,
                                "audio": str(audio)}
        report["status"] = "smoke_pass"
    except (Exception, KeyboardInterrupt) as exc:
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "error"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        save()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=tuple(MODEL_IDS))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--revision", default="main", help="Publisher revision; resolved SHA is recorded")
    parser.add_argument("--audio", type=Path, default=Path("outputs/question.wav"))
    parser.add_argument("--output", type=Path, default=Path("outputs/question.wav"))
    parser.add_argument("--report", type=Path, required=True, help="Private JSON result, including failures")
    args = parser.parse_args()
    result = benchmark(args.model, device=args.device, report_path=args.report,
                       audio=args.audio, output=args.output, revision=args.revision)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
