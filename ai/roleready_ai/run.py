"""CLI for real Qwen generation with an explicitly configured endpoint."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from .datasets import load_jsonl
from .generation import generate_questions
from .model import OpenAICompatibleQwen
from .retrieval import BGEFaissRetriever, LexicalRetriever

def run(*, input_file: Path, question_bank: Path, output_file: Path, retrieval_mode: str = "lexical") -> dict[str, object]:
    data = json.loads(input_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object.")
    records = load_jsonl(question_bank, split="train")
    if not records:
        raise ValueError("Question bank must contain training records.")
    if retrieval_mode == "lexical":
        retriever = LexicalRetriever(records)
    elif retrieval_mode == "bge-faiss":
        retriever = BGEFaissRetriever(records)
    else:
        raise ValueError("Choose lexical or bge-faiss.")
    model = OpenAICompatibleQwen()
    start = time.perf_counter()
    result = generate_questions(
        model=model, retriever=retriever, cv_text=str(data["cv_text"]),
        job_description=str(data["job_description"]),
        role=str(data["target_role"]), experience_level=str(data["experience_level"])
    )
    report = {
        "target_role": data["target_role"],
        "experience_level": data["experience_level"],
        "model_id": result.model_id,
        "retrieval_mode": retrieval_mode,
        "generation_mode": result.mode,
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "retrieved_source_ids": result.retrieved_source_ids,
        "questions": [asdict(question) for question in result.questions],
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate seven RoleReady questions with configured Qwen.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retrieval", choices=["lexical", "bge-faiss"], default="lexical")
    args = parser.parse_args()
    report = run(input_file=args.input, question_bank=args.bank, output_file=args.out, retrieval_mode=args.retrieval)
    print(f"Wrote {len(report['questions'])} questions using {report['model_id']} ({report['latency_ms']}ms).")

if __name__ == "__main__":
    main()
