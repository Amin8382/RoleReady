"""CLI smoke tests for optional voice models, no automatic downloads at import."""
from __future__ import annotations
import argparse
from pathlib import Path
from .voice import synthesize_question, transcribe_english


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    stt = sub.add_parser("transcribe")
    stt.add_argument("--audio", type=Path, required=True)
    stt.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    tts = sub.add_parser("speak")
    tts.add_argument("--text", required=True)
    tts.add_argument("--out", type=Path, required=True)
    tts.add_argument("--voice", default="af_heart")
    args = parser.parse_args()
    if args.command == "transcribe":
        result = transcribe_english(args.audio, device=args.device)
        print(result.text)
    else:
        print(synthesize_question(args.text, args.out, voice=args.voice))


if __name__ == "__main__":
    main()
