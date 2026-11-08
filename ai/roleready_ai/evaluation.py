"""Quality checks for the candidate question-generation model.

No external inference is triggered by this command. Metrics are structural and
lexical; human review is essential to assess factuality and real role relevance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable


def summarize_predictions(rows: Iterable[dict[str, Any]]) -> dict[str, object]:
    cases = 0
    structurally_valid = 0
    duplicates = 0
    invented_sources = 0
    overlap = 0
    by_role: Counter[str] = Counter()
    for item in rows:
        cases += 1
        by_role[str(item.get("target_role", "unknown"))] += 1
        questions = item.get("questions", [])
        if not isinstance(questions, list):
            questions = []
        texts = [
            str(question.get("text", "")).strip().casefold()
            for question in questions if isinstance(question, dict)
        ]
        if len(texts) == 7 and len(set(texts)) == 7 and all(len(text) >= 12 for text in texts):
            structurally_valid += 1
        duplicates += max(0, len(texts) - len(set(texts)))
        allowed = set(item.get("retrieved_source_ids", []))
        for question in questions:
            if not isinstance(question, dict):
                continue
            if set(question.get("source_ids", [])) - allowed:
                invented_sources += 1
            if str(item.get("target_role", "")).casefold() in str(question.get("text", "")).casefold():
                overlap += 1
    return {
        "cases": cases,
        "valid_seven_distinct_rate": round(structurally_valid / cases, 4) if cases else None,
        "duplicate_questions": duplicates,
        "questions_citing_unretrieved_sources": invented_sources,
        "role_string_mentions": overlap,
        "by_role": dict(sorted(by_role.items())),
        "note": "These automatic checks do NOT measure question factuality, relevance or interview value. Use two human reviewers on held-out cases.",
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError(f"Line {number} must contain a JSON object")
            result.append(parsed)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate non-LLM structural question quality checks.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize_predictions(read_jsonl(args.predictions))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
