# RoleReady

English interview preparation from a CV and a target job description: evidence-based preparation priorities, seven questions, voice practice, feedback and a PDF preparation sheet.

Team: Mohamed Amin Guesmi (AI/data), Oussema Ferchichi (API/scoring), Khaled Briki (web/voice).

## Clean rebuild

The team approved replacing the previous application on 8 November 2026. This repository is the record of the rebuild. The old application is recoverable from Git history. No generated scores are substituted when a model fails.

| Location | Purpose |
| --- | --- |
| `apps/web` | Next.js and TypeScript interface |
| `services/api/src/roleready` | FastAPI service, session storage and model adapters |
| `configs` | Pinned dataset sources and model configuration |
| `data` | DVC-managed downloads and prepared records; no candidate CVs in Git |
| `reports` | Reproducible public-data metrics and experiment summaries |
| `tests` | Data, API, isolation and model-contract tests |
| `docs` | Decisions, progress, failures, setup and team responsibilities |

Implementation and verified commands are recorded as milestones in [the progress log](docs/PROGRESS.md). Model research and its limitations are preserved in [the research notes](docs/research/README.md).

## Run locally

Requires Node.js 22, Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/). Commands work from the repository root; use three terminals for the API, web app and optional MLflow UI.

```bash
uv sync --frozen --extra dev --extra retrieval
npm ci
uv run --no-sync dvc repro
```

Copy `.env.example` to `.env`, and `apps/web/.env.example` to `apps/web/.env.local`. PowerShell: `Copy-Item .env.example .env` and `Copy-Item apps/web/.env.example apps/web/.env.local`.

For immediate question-bank exploration, set `ROLEREADY_QUESTION_MODE=retrieval` in `.env`. This explicitly skips generated gap analysis. For the full workflow, keep `llm` and connect the two model endpoints in [setup](docs/SETUP.md).

```bash
# Terminal 1: API
uv run --no-sync uvicorn roleready.api:app --host 127.0.0.1 --port 8000
# Terminal 2: web app
npm run dev
# Terminal 3: optional local experiment dashboard
uv run --no-sync mlflow server --backend-store-uri sqlite:///.state/mlflow.db --host 127.0.0.1 --port 5000
```

Open http://127.0.0.1:3000. API documentation: http://127.0.0.1:8000/docs. Experiments: http://127.0.0.1:5000.

The first data run downloads three pinned sources and the BGE embedding model, then indexes 16,299 training questions. Model caches and data are kept outside Git. Subsequent DVC runs skip unchanged stages.

## What works, what needs connecting

| Area | State |
| --- | --- |
| English interface, CV parsing, seven-question session, transcript editing, saved feedback, PDF | Implemented; backend, production build and complete browser workflow verified |
| BGE + FAISS retrieval, TF-IDF comparison, checksum audit, DVC, local MLflow | Executed on real public data; results in `reports/` |
| Qwen generation and Prometheus evaluation | Separate adapters implemented; live endpoints and interview-quality calibration still required |
| Whisper + Kokoro | Real local speech-to-transcript round trip passed; broader voice evaluation still needed |
| Supabase | Sign-in, server verification, persistence adapter and RLS migration implemented; live project credentials required |
| DagsHub | MLflow compatibility and connection check implemented; remote repository/token required |
| Custom LoRA fine-tuning | Reviewed CV/job/question pairs still required; no custom adapter trained or claimed |
| Payments | Deferred beyond the academic MVP |

The default app returns a clear service error when a required model is missing. Synthetic fixtures exist only in `tests/` for automated checks; they are never a production fallback.

## Team handbook

- [Setup and service connections](docs/SETUP.md)
- [Architecture and workflow](docs/ARCHITECTURE.md)
- [Data, experiments and evaluation](docs/DATA_AND_EVALUATION.md)
- [Team ownership and next milestones](docs/TEAM.md)
- [Progress, failures and fixes](docs/PROGRESS.md)

## Verify a change

```bash
uv run --no-sync ruff check services tests
uv run --no-sync ruff format --check services tests
uv run --no-sync pytest -q
npm run typecheck
npm run test:web
npm run build
npx playwright install chromium
npx playwright test
```

Browser tests launch a separate synthetic fixture server on port 8001 and the production web build on port 3100. Their purpose is workflow verification, not model evaluation. GitHub Actions runs the same checks without downloading model weights.

## Working agreement

Every meaningful change is committed. Each milestone records what changed, what was tested, what failed and what remains. Experiments log parameters, dataset/model versions, metrics and outcomes to MLflow. Git contains code and reports; DVC tracks larger data; credentials and candidate content stay out of both public Git and experiment logs.

The GitHub account can push code but cannot rename this repository. The owner must rename `interview_wingman` to `roleready` in repository settings. No new owner or duplicate repository is created automatically.
