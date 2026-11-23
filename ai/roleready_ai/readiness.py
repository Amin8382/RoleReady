"""Offline readiness inventory; no models or personal files are uploaded."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .model_registry import offline_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect five-model setup without downloading weights")
    parser.add_argument("--out", type=Path, help="Optional private JSON report")
    args = parser.parse_args()
    report = offline_report()
    value = json.dumps(report, indent=2, ensure_ascii=False)
    print(value)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(value + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
