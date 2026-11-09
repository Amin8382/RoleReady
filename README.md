# RoleReady — English interview preparation

**Team:** Mohamed Amin Guesmi · Oussema Ferchichi · Khaled Briki

RoleReady is an academic multimodel interview-preparation project. It helps a candidate prepare for English-language software, data and AI interviews using a resume and a target job description, a bank of relevant questions, voice practice and a structured feedback report.

> **Development status:** The Next.js app is a **demo frontend**, the FastAPI backend is a **stateless baseline**, and the AI/data package contains actual data tooling, optional BGE/FAISS retrieval, and an opt-in Qwen endpoint adapter. Models are NOT wired into the end-to-end app. Voice, authentication, persistence, verified scoring and PDF report are not implemented yet. Do not treat demo scores as AI evaluation.

## Repository layout

| Folder | Description | Lead |
| --- | --- | --- |
| app/ and lib/ | Next.js UI, resume parsing, typed interview demo | Khaled Briki (frontend/voice owner) |
| backend/ | FastAPI session contract, typed data, score endpoint (501 until model configured) | Oussema Ferchichi |
| ai/ | Reproducible data preparation, retrieval, Qwen adapter, quality checks, LoRA input preparation | Mohamed Amin Guesmi |
| docs/ | Project handoffs, rubric, architectural agreements | Team |
| .github/ | Continuous integration and pull-request template | Team |

## Quick start

Requires Node.js 20+ and Python 3.10+.

Frontend (from repository root):

    npm install
    npm run dev

Backend (in a second terminal):

    cd backend
    python -m pip install -r requirements-dev.txt
    uvicorn app.main:app --reload --port 8000

AI/data (in another terminal):

    cd ai
    python -m pip install -e ".[test]"
    python -m pytest -q

See [AI documentation](ai/README.md) and [backend documentation](backend/README.md) for dataset curation and the API. Visit http://localhost:3000 for the frontend and http://localhost:8000/docs for backend documentation.

**The frontend does not yet call the FastAPI service.** The AI package does not download or serve Qwen automatically. You must explicitly configure a compatible inference endpoint to generate questions with the live model.

## Candidate architecture

- Qwen3.5 4B — local quantized question generation verified; analysis/report integration and quality validation pending
- Prometheus 7B v2 — rubric-based answer evaluation, owned by backend workstream (candidate; not integrated)
- BGE-small-en-v1.5 — embeddings; FAISS — vector index (optional real implementation in ai/)
- Whisper small English — optional speech-to-text adapter; not wired into the app
- Kokoro 82M — optional English narration adapter; not wired into the app
- Supabase — private accounts/files/sessions (planned)
- FastAPI and Next.js — service/frontend components (present as independent baselines)

Models and dataset counts come from the team overview and must be verified against original publishers, licensing and target hardware before production. FAISS is not a model.

BGE/FAISS, Whisper and Kokoro passed real CPU/CUDA smoke checks on the local
Windows RTX 4080 Laptop machine. The [environment evidence report](ai/docs/LOCAL_ENVIRONMENT_2026-11-09.md)
records installation, exact versions, timings and remaining blockers.
[Mission 002](ai/docs/MISSION_002_QWEN_RAG.md) subsequently verified local Qwen3.5
4B Q4_K_M generation: three synthetic scenarios with lexical and BGE/FAISS
retrieval each produced seven structurally valid questions. Samples retain
explicit quality findings. Prometheus inference, validated scoring and end-to-end
product integration remain unfinished.

## Collaboration

- [Contributing guide](CONTRIBUTING.md)
- [Shared team implementation contracts](docs/TEAM_IMPLEMENTATION.md)
- [Evaluation rubric](docs/SCORING_RUBRIC.md)
- [AI/data package guide](ai/README.md)

Use feature branches and reviewed PRs. Never commit personal CVs, voice recordings, API keys, private reports or unreviewed/unlicensed external datasets. AI outputs must be grounded with source IDs and labeled by mode. CI runs frontend, backend and AI checks on changes.

## Development gates

1. Contract/data preparation, sources and tests
2. Live CV/job analysis, retrieved seven questions and **real** typed scoring
3. Spoken questions, editable transcripts, private sessions and PDF
4. Two-reviewer held-out evaluations, model comparison, optional LoRA and demonstration

**Not yet achieved:** live-model benchmark, 30-case human review, trained LoRA, or verified production end-to-end session.
