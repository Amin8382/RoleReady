# Progress and experiment log

## 2026-11-08 M0 Clean rebuild authorised

- Confirmed English scope, the seven-question workflow and the three-member work split.
- Inspected both old frontend variants. The root app silently substituted sample analysis, transcripts and scores; PDF upload did not extract actual text.
- **Failure:** the old `npm ci` failed with `ERESOLVE`: ESLint 9 conflicted with the Next.js 14 ESLint package. No dependencies were forced into an incompatible installation.
- **Decision:** the user explicitly requested removal of all old application files and a clean RoleReady rebuild. Removed those tracked files on `feat/roleready-platform`; Git history is preserved.
- Imported prior model research, eight-case exploratory generation outputs and pinned dataset source metadata. Research results are not a production benchmark.
- **Access limitation:** GitHub API reports push permission but no admin permission. The settings page says the account cannot access repository options. Repository rename requires the owner.
- Environment available for validation: CPU only, approximately 9.7 GiB RAM. No Supabase, model API or DagsHub credentials were configured.
- Next milestone: reproducible data preparation, DVC stages, retrieval comparison and MLflow runs.

## 2026-11-08 M1 Data pipeline in progress

- Verified immutable revisions and SHA-256 for all three selected sources.
- Prepared 21,005 unique questions: 20,444 synthetic question-bank records, 531 supplemental Q&A records and 30 isolated evaluation records. Removed 35 repeated supplemental questions.
- The retrieval bank uses 16,299 training-split synthetic questions; validation/test splits and the external evaluation set are excluded. Supplemental answers remain excluded pending provenance review.
- Preserved source-specific categories, difficulty, reference concepts and evaluation rubrics.
- MLflow now records run status, Git revision, dirty-tree status, parameters, counts and safe artifacts. Added a DVC pipeline and eight explicitly provisional retrieval queries.
- **Failure:** the first BGE model load could not use the environment's SOCKS proxy because `socksio` was absent. The run is recorded as FAILED in MLflow. Added the `httpx[socks]` dependency; retried without disabling network or TLS protections.

## 2026-11-08 M1 Data and retrieval verified

- Built a real BGE/FAISS index: 16,299 questions, 384 dimensions. CPU encoding took approximately 8 minutes.
- Ran the same eight exploratory queries against TF-IDF and BGE. Hit@5: 0.75 vs 1.00; MRR@5: 0.6042 vs 1.00. These are provisional, assistant-authored query labels with incomplete relevance judgments, not a general quality benchmark. BGE first-query model loading is included in average latency.
- Registered already-executed pipeline outputs with `dvc commit --force`; `dvc repro` then confirmed all four stages were current. No remote data storage is configured yet.
- Isolated the deliberately failing checksum test's experiment reports in its temporary directory so test fixtures cannot contaminate public experiment evidence.

## 2026-11-08 M2 Application workflow implemented

- Added FastAPI orchestration, validated seven-question outputs, exact-source evidence checks, separate generator/evaluator clients and explicit missing-service errors.
- Added local SQLite sessions, Supabase user verification and an owner-scoped RLS migration. Concurrent writes use version checks. Supabase has contract tests but is not connected to a live project.
- Added CV extraction, original/corrected transcripts, real scoring contracts, report invalidation after edits, session deletion and PDF cheat sheets derived from saved feedback.
- Built the new English Next.js interface, same-origin API proxy, optional sign-in, microphone recording, transcript editing, resumable sessions and PDF download.
- Validation so far: 15 Python tests passed; TypeScript passed; production web build passed. Browser checks are in progress.
- **Voice experiment:** Kokoro generated a real WAV. Transcription then failed because PyAV 19 removed an argument still used by faster-whisper 1.2.1. Recorded the failed MLflow run and constrained PyAV below 19. Pinned Kokoro's English language package instead of relying on an implicit download.
- **Browser setup failure:** Playwright's first Chromium archive download was incomplete. Investigating/retrying installation; no browser pass claimed yet.
