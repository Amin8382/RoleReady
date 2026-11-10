"""Opt-in smoke checks. Only selected model loads, and weights may download."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time


def smoke(name: str, audio: Path | None = None, output: Path | None = None) -> dict:
    start = time.perf_counter()
    if name == "qwen":
        from .model import OpenAICompatibleQwen
        model = OpenAICompatibleQwen()
        result = model.complete_json(
            system='Reply with JSON object {"ok": true} only.',
            user="Connectivity check on synthetic text.",
        )
        if result.get("ok") is not True:
            raise ValueError("Qwen response failed structured JSON validation.")
        details = {"model_id": model.model, "structured_json": True}
    elif name == "prometheus":
        from .scoring import PrometheusEvaluator
        report = PrometheusEvaluator.from_env().evaluate(
            question="How did you validate your SQL pipeline?",
            corrected_transcript="I compared query plans and measured latency for sample queries.",
            reviewed_reference_answer="Compare explain plans, correctness tests, and measured query latency.",
        )
        details = {"model_id": report.model_id, "dimension_count": len(report.dimensions),
                   "calibrated": False}
    elif name == "bge":
        from .datasets import QuestionRecord
        from .retrieval import BGEFaissRetriever
        record = QuestionRecord(
            record_id="sample", question="How do you test a machine learning pipeline?",
            role="Machine Learning Engineer", source_id="synthetic", split="train",
        )
        engine = BGEFaissRetriever([record])
        matches = engine.search(query="ML model testing", role="Machine Learning Engineer", k=1)
        if len(matches) != 1 or matches[0].record.record_id != "sample":
            raise RuntimeError("BGE/FAISS retrieval failed.")
        details = {"model_id": engine.model_name, "hits": len(matches)}
    elif name == "kokoro":
        if output is None:
            raise ValueError("--output is required for kokoro")
        from .voice import synthesize_question
        result = synthesize_question("Tell me about an engineering project you built.", output)
        details = {"model_id": "hexgrad/Kokoro-82M", "output": str(result)}
    elif name == "whisper":
        if audio is None:
            raise ValueError("--audio is required for whisper")
        from .voice import transcribe_english
        result = transcribe_english(audio)
        details = {"model_id": result.model_id, "transcript": result.text}
    else:
        raise ValueError("Unknown model")
    return {
        "name": name, "status": "smoke_pass", "duration_ms": round((time.perf_counter()-start)*1000),
        **details, "warning": "Smoke only, not quality or production validation",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("model", choices=["qwen", "prometheus", "bge", "kokoro", "whisper"])
    p.add_argument("--audio", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    print(json.dumps(smoke(args.model, audio=args.audio, output=args.output), indent=2))


if __name__ == "__main__":
    main()
