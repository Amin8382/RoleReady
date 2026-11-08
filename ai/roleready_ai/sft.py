"""Generate supervised fine-tuning records from independently human-reviewed cases.

This is data export for a *future* Qwen LoRA comparison. It does not train a
model or pretend to have measured LoRA performance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .datasets import load_jsonl


def export_sft(*, source: Path, out: Path) -> int:
    """Only manually reviewed TRAIN records with a reference answer are eligible."""
    records = load_jsonl(source, split="train")
    rows = [
        {
            "messages": [
                {"role": "system", "content": "Answer this English interview question accurately and concisely."},
                {"role": "user", "content": record.question},
                {"role": "assistant", "content": record.reference_answer},
            ],
            "source_id": record.source_id,
            "record_id": record.record_id,
        }
        for record in records if record.reviewed and record.reference_answer
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reviewed-only TRAIN SFT cases.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    count = export_sft(source=args.input, out=args.out)
    print(f"Exported {count} independently reviewed training examples; no model trained.")


if __name__ == "__main__":
    main()
