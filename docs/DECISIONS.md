# Decisions

## ADR 001 Clean English product

RoleReady replaces both previous app variants. Start with software, data and AI interview roles. The user's explicit English correction supersedes the old multilingual pitch. Paid subscriptions are outside the first academic release.

## ADR 002 Separate responsibilities

Next.js owns the interface and same-origin API proxy. FastAPI orchestrates Python models and session persistence. Qwen generates; Prometheus evaluates; BGE retrieves; Whisper transcribes; Kokoro speaks. FAISS is an index, not a model.

## ADR 003 Evidence before quality claims

The Qwen and Prometheus choices are candidates. The evaluator needs human interview calibration. A general question bank is not a CV-conditioned fine-tuning dataset. Train a LoRA adapter only on reviewed paired examples and compare it against the unchanged backbone on held-out cases.

## ADR 004 Reproducible data and experiments

Download source files at immutable revisions and verify SHA-256. Record provenance, source licence metadata, duplicate removal and split rules. Keep the 30-item benchmark isolated. MLflow records public-data experiment metadata and failed outcomes; it does not log candidate CVs or answers. DVC owns large derived files. Git owns code, small reports and explanations.

## ADR 005 Development and hosted operation

Provide a local single-user development mode and a fail-closed Supabase mode for hosted use. Local mode must not be advertised as authentication. Real model endpoints or optional local model adapters must return errors when unavailable. No silent fallback scoring.
