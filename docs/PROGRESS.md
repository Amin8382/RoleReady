# Progress and experiment log

**Current working repository: https://github.com/Amin8382/RoleReady.** The assistant's earlier repository selection was wrong. M0–M4 below describe the work completed before that correction; their original commit and CI links remain historical evidence. The previous rename blocker does not apply to this repository.

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

## 2026-11-08 M3 Integration fixes and real voice verification

- Retried the voice round trip with PyAV 18.1.0. Kokoro generated a 241,244-byte WAV and Whisper transcribed the public test sentence exactly. This verifies connectivity for one synthetic sentence, not accent/technical-speech accuracy. Exported the successful MLflow run and `reports/voice_smoke.json`.
- GitHub CI passed Python tests, TypeScript and production build. Its first browser run caught a real upload failure: Next.js normalized its internal URL host, causing valid local browser origins to fail the proxy's origin check. Fixed browser-facing host validation while retaining cross-origin and DNS-rebinding rejection; added four regression tests.
- Fixed a browser-test locator that also matched Next.js's route-announcement alert.
- The local headless browser cannot create a required Unix socket in this environment. Browser verification continues through GitHub Actions rather than changing the environment's security controls.
- Added a direct team handbook covering startup, model endpoints, Supabase/RLS, DagsHub, data limitations and the fine-tuning gate. DagsHub connection check confirms the remote URI is not configured.

## 2026-11-08 M4 Clean rebuild verified for integration

- GitHub Actions run [42492017126](https://github.com/Aminebenfadhel14/interview_wingman/actions/runs/42492017126) passed on `071be40b23e567b005921c58aadb459b7dcd025d`: 15 Python tests, four web regression tests, TypeScript, production build and two Chromium browser tests.
- Browser coverage includes real document parsing through the proxy, seven scored fixture answers, reload/resume, report creation, PDF download, deletion, mobile layout and retained inputs after a model error. Synthetic model fixtures are confined to test code; these checks do not certify Qwen or Prometheus output quality.
- Verified an actual BGE-backed API session using a synthetic CV/JD: HTTP 201, exactly seven retrieved questions, no claimed generated gap analysis. An unconfigured evaluator returned HTTP 503 and created zero fake answers. Saved `reports/real_api_smoke.json` and the MLflow run.
- Reviewed desktop/mobile layout captures and added mobile access to saved sessions. No candidate data was used in testing.
- All old application files have been replaced on the rebuild branch. The PR is ready for integration with milestone commits preserved. GitHub records the subsequent merge outcome.
- Still external: repository owner must rename the repository; team must connect real Qwen/Prometheus serving, Supabase and DagsHub. Fine-tuning waits for reviewed CV/job pairs and a compatible GPU environment.

## 2026-11-08 M5 Correct repository selected; import prepared

- The user explicitly identified **Amin8382/RoleReady** as the working repository. The assistant acknowledges that selecting `Aminebenfadhel14/interview_wingman` was an error.
- Verified repository ID `1435056976`, owner `Amin8382`, default branch `main` and the user's administrator/write permissions. The destination initially contains only its README and initial commit `36aebfee44a09fb1a0e9ad09a17f3fd21b9b8631`.
- Corrected the local `origin` URL. Prepared an import branch based on the destination's initial commit, replaying all four clean-build milestones without importing the old application's history. The imported 85-file source tree exactly matches the previously tested build before repository-specific documentation changes.
- Added a repository identity check to `AGENTS.md` and corrected current setup/README guidance. `docs/repository-import.json` maps the original milestone commits to their local imported counterparts.
- **Publishing blocker:** GitHub returned HTTP 403, `Resource not accessible by integration`, on branch creation. Installation discovery shows the connected app is installed only under `Aminebenfadhel14`; it has no installation for `Amin8382`. The user's admin rights and the app's installation permissions are distinct.
- The transfer is prepared locally but has **not been published** to the destination. After connecting the GitHub app to `Amin8382/RoleReady`, publish this branch, run CI in the correct repository and integrate through a pull request.

## 2026-11-08 M6 GitHub access restored; import and concurrent work review

- Several retries still returned HTTP 403 until the user installed ChatGPT Codex Connector on **Amin8382**. Authorization of the user's identity and installation on the repository owner were separate steps. Verified installation `179900517` and successfully created `feat/import-verified-platform` in repository `1435056976`.
- The first resumed access check was interrupted. A fresh check found two newer draft PRs: [MVP/backend contracts #1](https://github.com/Amin8382/RoleReady/pull/1) and [Amin AI/data work #2](https://github.com/Amin8382/RoleReady/pull/2). Both target `main`, which remains at the initial README commit.
- Transferred the four build milestones and the repository correction through the GitHub connector. Every uploaded tree hash matches its local source tree. Updated `repository-import.json` with the actual GitHub commit IDs; original experiment IDs remain historical evidence.
- Kept this import on its own branch. Existing branches, PRs and `main` have not been overwritten, merged or closed. Their different layouts and API contracts require deliberate reconciliation; see `INTEGRATION_STATUS.md`.
- Updated setup and clone instructions for the import branch. Fresh destination CI is the remaining validation gate; the original successful checks do not stand in for a run in this repository.
