"""CLI for real Qwen generation with an explicitly configured endpoint."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from .datasets import load_jsonl
from .generation import generate_questions, QUESTION_RESPONSE_SCHEMA
from .model import OpenAICompatibleQwen
from .retrieval import BGEFaissRetriever, LexicalRetriever
from .retrieval import EmptyRetriever, BGE_REVISION
from .corpus import load_corpus
from .acquisition import file_sha256

def run(*, input_file: Path, question_bank: Path, output_file: Path, retrieval_mode: str = "lexical",
        bank_format: str = "legacy-train", index_path: Path | None = None) -> dict[str, object]:
    data = json.loads(input_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object.")
    if bank_format not in {"legacy-train", "corpus"}:
        raise ValueError("Choose legacy-train or corpus bank format")
    records = load_corpus(question_bank) if bank_format == "corpus" else load_jsonl(question_bank, split="train")
    if not records:
        raise ValueError("Question bank must contain eligible corpus or legacy training records.")
    if index_path is not None and (bank_format != "corpus" or retrieval_mode != "bge-faiss"):
        raise ValueError("A persisted index requires corpus format and bge-faiss retrieval")
    if retrieval_mode == "none":
        retriever = EmptyRetriever()
    elif retrieval_mode == "lexical":
        retriever = LexicalRetriever(records)
    elif retrieval_mode == "bge-faiss":
        retriever = (BGEFaissRetriever.load(index_path, expected_corpus_sha256=file_sha256(question_bank),
                                           expected_model_revision=BGE_REVISION) if index_path is not None
                     else BGEFaissRetriever(records, corpus_sha256=file_sha256(question_bank) if bank_format == "corpus" else None))
    else:
        raise ValueError("Choose none, lexical or bge-faiss.")
    model = OpenAICompatibleQwen(response_schema=QUESTION_RESPONSE_SCHEMA)
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
        "attempts": result.attempts,
        "rejected_attempts": result.rejected_attempts,
        "endpoint_response": model.last_response,
        "quality_status": result.quality_status,
        "quality_warning": "Literal evidence and valid citations do not certify question claims or reference criteria; review before use.",
        "bank_format": bank_format,
        "corpus_sha256": file_sha256(question_bank) if bank_format == "corpus" else None,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate seven RoleReady questions with configured Qwen.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retrieval", choices=["none", "lexical", "bge-faiss"], default="lexical")
    parser.add_argument("--bank-format", choices=["legacy-train", "corpus"], default="legacy-train")
    parser.add_argument("--index", type=Path, help="Trusted persisted corpus index, for bge-faiss only")
    args = parser.parse_args()
    report = run(input_file=args.input, question_bank=args.bank, output_file=args.out, retrieval_mode=args.retrieval,
                 bank_format=args.bank_format, index_path=args.index)
    print(f"Wrote {len(report['questions'])} questions using {report['model_id']} ({report['latency_ms']}ms).")

if __name__ == "__main__":
    main()
