# RoleReady FastAPI — phase 1 baseline

Requires Python 3.10+.

```bash
cd backend
python -m venv .venv
# Activate .venv using your operating system's method
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs).

```bash
# From backend/
PYTHONPATH=. pytest -q
```

On Windows PowerShell: `$env:PYTHONPATH="."; pytest -q`.

### Endpoints

- `GET /health`: service health and active baseline mode.
- `POST /api/v1/sessions`: input validation and seven deterministic baseline questions.
- `POST /api/v1/evaluations`: HTTP 501 `MODEL_NOT_CONFIGURED`, deliberately no manufactured score.

Example session request:

```json
{
  "target_role": "Machine Learning Engineer",
  "experience_level": "junior",
  "cv_text": "I built several machine learning projects with Python and pandas.",
  "job_description": "We seek an engineer with experience in Python, SQL, Docker and data analysis."
}
```

This endpoint is stateless: a session identifier is created but **not persisted**. Model integration, actual RAG, authentication, private storage, live voice, and report PDF export remain unimplemented. Restrict public deployment until these are added. CORS currently permits only `http://localhost:3000`.

### Testing

The backend's four initial tests have passed in an isolated Python environment with FastAPI 0.128.2, Pydantic 2.13.5 and pytest 9.0.2. Frontend compilation and an integrated session have **not** yet been verified.
