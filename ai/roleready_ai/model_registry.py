"""Verified canonical model IDs and honest, offline readiness inspection.

Checking installed Python packages does NOT prove that the corresponding
weights are cached or that a model can perform inference.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import json
import os
import platform
import sys
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model_id: str
    responsibility: str
    publisher_url: str
    expected_license: str
    backend: str
    dependency: str | None
    endpoint_env: str | None


MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        "qwen", "Qwen/Qwen3.5-4B", "CV/job analysis and seven-question generation",
        "https://huggingface.co/Qwen/Qwen3.5-4B", "apache-2.0", "OpenAI-compatible chat",
        None, "ROLEREADY_QWEN_BASE_URL",
    ),
    ModelSpec(
        "prometheus", "prometheus-eval/prometheus-7b-v2.0", "Rubric-based answer scoring",
        "https://huggingface.co/prometheus-eval/prometheus-7b-v2.0", "apache-2.0",
        "OpenAI-compatible chat", None, "ROLEREADY_PROMETHEUS_BASE_URL",
    ),
    ModelSpec(
        "bge", "BAAI/bge-small-en-v1.5", "English question embeddings for FAISS search",
        "https://huggingface.co/BAAI/bge-small-en-v1.5", "mit", "sentence-transformers + FAISS",
        "sentence_transformers", None,
    ),
    ModelSpec(
        "whisper", "Systran/faster-whisper-small.en", "English speech recognition",
        "https://huggingface.co/Systran/faster-whisper-small.en", "mit",
        "faster-whisper / CTranslate2", "faster_whisper", None,
    ),
    ModelSpec(
        "kokoro", "hexgrad/Kokoro-82M", "Read questions aloud in English",
        "https://huggingface.co/hexgrad/Kokoro-82M", "apache-2.0",
        "KPipeline (Kokoro 0.9.4)", "kokoro", None,
    ),
)


def offline_report() -> dict[str, Any]:
    """NO downloads, HTTP calls, or model loading."""
    details: list[dict[str, Any]] = []
    for spec in MODELS:
        package_present = (
            importlib.util.find_spec(spec.dependency) is not None
            if spec.dependency else None
        )
        endpoint_configured = (
            bool(os.environ.get(spec.endpoint_env))
            if spec.endpoint_env else None
        )
        details.append({
            **asdict(spec),
            "package_installed": package_present,
            "endpoint_configured": endpoint_configured,
            "inference_verified": False,
            "note": (
                "Environment/configuration check ONLY. Model weights and inference not tested."
            ),
        })
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "recommended_python": "3.11",
        "kokoro_0_9_4_python_supported": (3, 10) <= sys.version_info[:2] < (3, 13),
        "models": details,
        "warning": "No model weight download, real inference, or hardware benchmark has occurred.",
    }


def format_report(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)
