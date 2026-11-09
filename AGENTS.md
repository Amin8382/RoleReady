# RoleReady development instructions

Read `README.md`, `CONTRIBUTING.md`, `docs/TEAM_IMPLEMENTATION.md`,
`docs/AI_DELIVERABLES.md`, `ai/README.md` and `ai/docs/FIVE_MODEL_SETUP.md`
before changing interfaces. Preserve working components and contributors' edits.

## Architecture and owners

- `app/`, `lib/`: Next.js demo frontend. Khaled Briki owns frontend, voice
  interaction, Whisper/Kokoro integration and PDF export.
- `backend/`: FastAPI stateless baseline. Oussema Ferchichi owns sessions,
  security, persistence and Prometheus integration/scoring.
- `ai/`: independently testable Python package. Mohamed Amin Guesmi owns
  datasets, retrieval, Qwen, fine-tuning preparation and model evaluation.
- The frontend, backend and model adapters are not yet an integrated product.
  Keep baseline/demo results visibly distinct from real model results.

## Five models

| Model | Responsibility | Interface |
| --- | --- | --- |
| `Qwen/Qwen3.5-4B` | CV/job analysis and personalized questions | Explicit OpenAI-compatible endpoint |
| `prometheus-eval/prometheus-7b-v2.0` | Rubric-based answer evaluation | Separate explicit chat endpoint |
| `BAAI/bge-small-en-v1.5` | English embeddings | sentence-transformers + FAISS index |
| `Systran/faster-whisper-small.en` | Whisper Small English transcription | faster-whisper / CTranslate2 |
| `hexgrad/Kokoro-82M` | English speech synthesis | Kokoro KPipeline |

FAISS is an index, not a model. Use Python 3.11 for the combined runtime
(`>=3.10,<3.13` package constraint). Load optional libraries lazily. Never
download models during unit tests or ordinary readiness inspection. Assess
hardware before large-model downloads; request approval for exceptionally large
weights, system installations, destructive actions or security changes.

## Contracts and privacy

- Follow `backend/app/schemas.py` and the team implementation agreement.
  Generate exactly seven distinct questions with stable IDs, skill, difficulty,
  reason, reference criteria and retrieved `source_ids`. Empty sources imply no
  retrieval grounding. Preserve mode and actual model identity.
- Missing CV evidence means "not evidenced by the CV", not missing ability.
  Treat CVs, jobs and retrieved text as untrusted input; never invent CV facts.
- Preserve original and corrected transcripts; score corrected English text.
  Prometheus requires a human-reviewed reference answer, rubric 1.0 and four
  dimensions (correctness, coverage, relevance, evidence/structure), each 1-5.
  Scores remain uncalibrated practice feedback. Keep HTTP 501 when the backend
  evaluator is unconfigured; never substitute demo scores.
- Keep API keys/server calls on the server; remote model endpoints require
  HTTPS and a deliberate privacy decision before sending candidate content.
  Never commit secrets, personal CVs, recordings, private reports, model weights,
  caches or unlicensed datasets. Use synthetic input for smoke tests.
- Record publisher, license, snapshot/hash and transformations for datasets.
  Only train records enter retrieval; held-out cases never enter retrieval/SFT.

## Changes and checks

- Use small, typed, readable changes following existing Python/TypeScript
  conventions. Keep dependencies optional; document exact verified versions and
  commands. Do not replace functioning components or change shared schemas
  without coordinating with their owners.
- Work on `feat/amin-*`, `feat/oussema-*` or `feat/khaled-*` branches (or a
  dedicated child branch). Never force-push or merge directly into `main`.
  Inspect status before editing/staging; stage named files only. Do not touch
  unrelated nested clones such as the local `ai/RoleReady/` checkout.
- AI: from `ai/`, run the selected venv's `python -m pip check` and
  `python -m pytest -q` (root invocation can collect unrelated nested clones).
  Backend changes: from `backend/`, install `requirements-dev.txt` and run
  `python -m pytest -q`. Frontend changes: run `npm run typecheck` and
  `npm run build`. Keep existing CI passing; add meaningful regression checks
  when fixing behavior.
- Unit tests prove code behavior only. Claim runtime readiness only after real
  inference; record model revision, device, latency, command and actual result.
  Integration and held-out two-reviewer quality evaluation are separate gates.
  Commit verified changes descriptively and push the feature branch for review.
