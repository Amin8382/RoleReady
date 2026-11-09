# RoleReady — Backend & Scoring Module

**Author / Module Lead:** Oussema Ferchichi  
**Teammates:** Mohamed Amin Guesmi (AI & Data Pipeline), Khaled Briki (Frontend & Voice)  
**Project:** RoleReady (AI-Powered English Technical & Behavioral Interview Preparation)  

---

## 1. Overview & Architecture

The RoleReady backend is a high-performance Python FastAPI service responsible for:
1. **API & Data Contracts**: Pydantic v2 schemas and validation for sessions, questions, answers, and reports.
2. **Scoring Engine**: Evaluates candidate answers using the **Prometheus 7B v2** model with an interchangeable architecture (`PrometheusScorer` / `MockScorer`) on a 1–5 practice rubric.
3. **Persistence & Access Control**: PostgreSQL/Supabase schema with **Row-Level Security (RLS)**, JWT authentication middleware, and an out-of-the-box local SQLite fallback engine.
4. **Integration Adapters**:
   - **Amin's Pipeline**: Function interfaces for Qwen 3.5 4B CV/job analysis and 7-question generation (`app/integrations/amin_pipeline.py`).
   - **Khaled's Voice**: Adapter endpoints for Whisper small STT and Kokoro 82M TTS (`app/integrations/khaled_voice.py`).

> **Ethical Calibration Principle**: Scores describe **practice performance on this specific attempt**, never the probability of being hired.

---

## 2. Directory Structure

```text
backend/
├── app/
│   ├── main.py                 # FastAPI application factory, CORS, exception handlers
│   ├── config.py               # Pydantic-Settings environment configuration
│   ├── auth/                   # JWT verification middleware & session isolation
│   ├── database/               # Database repository (SQLite fallback & Supabase client)
│   ├── schemas/                # Shared Pydantic v2 data models
│   ├── scoring/                # Scoring module (Prometheus 7B v2, MockScorer, Factory)
│   ├── integrations/           # Teammate interface adapters (Amin & Khaled)
│   └── routes/                 # REST endpoints (/sessions, /questions, /answers, /audio)
├── data/
│   ├── rubric_v1.json          # Shared 1-5 practice scoring rubric
│   └── eval_benchmark.csv      # 15 human-annotated calibration benchmark cases
├── migrations/
│   └── 001_initial_schema.sql  # Supabase database schema + RLS policies
├── scripts/
│   └── eval_scoring.py         # Scoring calibration benchmark script (MAE & Pearson r)
├── tests/                      # Pytest suite (validation, auth, scoring, full session)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. Quick Start & Setup

### 3.1 Create Virtual Environment & Install Dependencies

```bash
# In the project root (Windows PowerShell)
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### 3.2 Environment Configuration

Copy `.env.example` to `.env`:
```bash
cp backend/.env.example backend/.env
```

Default configuration runs in self-contained **local demo mode** (SQLite database, MockScorer for instant responses without needing local 7B GPU weights).

---

## 4. Switching Scorer Backends

The scoring engine is controlled by the `SCORER_BACKEND` environment variable in `backend/.env`:

| `SCORER_BACKEND` | Description |
|---|---|
| `mock` *(default)* | Deterministic, ultra-fast scorer based on keyword alignment and reference criteria. Ideal for demos, unit tests, and machines without 16GB+ VRAM. |
| `ollama` | Calls Prometheus 7B v2 running locally on Ollama (`http://localhost:11434/api/generate`). |
| `vllm` / `hf_api` | Calls Prometheus 7B v2 hosted on vLLM or Hugging Face Inference Endpoints. |

If Prometheus is unreachable or times out, `PrometheusScorer` automatically falls back to `MockScorer` with a warning log, ensuring zero demo interruptions.

---

## 5. Running the Backend Server

```bash
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 6. Running the Evaluation Benchmark

To run the calibration benchmark against the 15 human-annotated test cases:

```bash
.\venv\Scripts\python.exe backend/scripts/eval_scoring.py
```

Outputs:
- Individual case predictions vs human ground truth
- **Mean Absolute Error (MAE)**
- **Pearson Correlation Coefficient ($r$)**
- Category breakdown for Weak, Partial, and Strong answers

---

## 7. Running Tests

```bash
.\venv\Scripts\python.exe -m pytest backend/tests/ -v
```

11 automated tests verify:
- Input validation (empty, unsupported, and >5MB files rejected)
- JWT access control and candidate session isolation
- Prometheus regex output parsing and error resilience
- MockScorer score discrimination
- Full end-to-end interview session workflow
