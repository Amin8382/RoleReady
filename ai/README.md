# RoleReady AI & Data

**Owner:** Mohamed Amin Guesmi

This package implements an independently testable AI/data module. It is **not** a completed fine-tuned model, and no live-model evaluation has been completed.

## Layout

- roleready_ai/datasets.py — CSV/JSONL curation, normalized deduplication, deterministic grouped splits and manifest
- roleready_ai/retrieval.py — lexical baseline; optional BGE-small-en-v1.5 + FAISS retrieval
- roleready_ai/model.py — opt-in Qwen OpenAI-compatible server adapter
- roleready_ai/generation.py — seven-question schema, evidence-aware instructions and source-ID validation
- roleready_ai/run.py — end-to-end command-line generation
- roleready_ai/evaluation.py — structural checks on model outputs, not quality judgments
- roleready_ai/sft.py — guarded export of reviewed TRAIN cases; does **not** train
- data/sample_questions.csv — hand-authored synthetic examples only, **not a vetted production dataset**

## Install and test

Python 3.10+ is required. From repository root, run:

    cd ai
    python -m venv .venv
    # Activate your virtual environment for your OS
    python -m pip install -e ".[test]"
    python -m pytest -q

## Curate questions

    python -m roleready_ai.datasets --input data/sample_questions.csv --out data/processed/sample --source-id synthetic-example --source-url https://example.org/placeholder --license UNVERIFIED

The URL above is deliberately a **placeholder**, not genuine source provenance. For a third-party dataset, record its actual URL, license and hash and check usage permissions before publishing/training. Freshly curated rows are always unreviewed. The question-normalized split is stable across duplicate roles to protect held-out cases.

## Optional semantic retriever

    python -m pip install -e ".[retrieval,test]"

BGE-small-en-v1.5 requires model weights, which may download from Hugging Face on first load. FAISS is a vector index, not a language model. The lexical retriever is a dependency-light baseline; it is not semantic search.

## Live Qwen inference (explicit opt-in)

Start a compatible Qwen inference server and configure the actual served model identifier. The candidate name and server interface must be verified against the model host. Example environment on macOS/Linux:

    export ROLEREADY_QWEN_BASE_URL=http://127.0.0.1:8001/v1
    export ROLEREADY_QWEN_MODEL=YOUR_EXACT_SERVED_MODEL_ID
    # Optionally export ROLEREADY_QWEN_API_KEY as required by your server
    python -m roleready_ai.run --input examples/sample_session.json --bank data/processed/sample/train.jsonl --out outputs/sample_generation.json --retrieval lexical

Use "--retrieval bge-faiss" to enable the semantic retriever. On Windows PowerShell: $env:ROLEREADY_QWEN_BASE_URL="http://127.0.0.1:8001/v1" (and similarly for model ID). No weights, paid account, or public endpoint are bundled. Model calls fail explicitly without endpoint configuration.

**Privacy:** Input/output files can contain candidate CV data. Keep these local and private. Outputs, raw datasets and generated model artifacts must never be committed by default.

## Evaluation and LoRA preparation

On about 30 held-out CV/job pairs, compare non-ML baseline, Qwen without retrieval, Qwen with lexical retrieval, and Qwen with BGE/FAISS. Later compare a reviewed LoRA adapter with the same held-out cases. Log model versions, prompts, latency, exceptions and machine use. Two independent reviewers should assess relevance, personalization, correctness and variety. Never retrieve from held-out examples.

For generated question records in JSONL:

    python -m roleready_ai.evaluation --predictions outputs/predictions.jsonl --out outputs/metrics.json

Later, after manual review and licensing checks, export training-only Q&A:

    python -m roleready_ai.sft --input data/processed/sample/train.jsonl --out outputs/reviewed_train.jsonl

The SFT exporter currently produces general interview Q&A training pairs, **not** personalized CV/job/question triplets. A RoleReady-specific LoRA training implementation is not yet present and must not be claimed as complete.

## Team handoff

Mohamed Amin owns AI/data; Oussema owns FastAPI and Prometheus evaluator; Khaled owns Next.js and voice. Shared schemas and ownership live in ../docs/TEAM_IMPLEMENTATION.md. The FastAPI baseline is not automatically connected to Qwen. Run tests and validate model outputs on real target hardware before integration.

## Five-model runtime integration

The five model adapters, optional voice dependencies, offline readiness inventory and per-model smoke commands are documented in [the Windows five-model setup guide](docs/FIVE_MODEL_SETUP.md). Run `python -m roleready_ai.readiness` to inspect dependencies without downloading model weights. Runtime checks are opt-in via `python -m roleready_ai.model_smoke <model>`. The repository does not include large model weights, does not host Qwen or Prometheus inference servers, and does not claim completed end-to-end integration or calibrated scoring.
