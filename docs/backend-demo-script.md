# Technical Validation Demo Script (Backend & Scoring Lead)

**Presenter:** Oussema Ferchichi  
**Audience:** Jury & Technical Validation Evaluators  
**Estimated Time:** 5–7 minutes  

---

## 1. Introduction & Responsibilities (30 seconds)
> *"Hello everyone. In RoleReady, I am responsible for the **Backend and Scoring Module**. My role is to coordinate the data contracts between Amin's AI pipeline and Khaled's frontend, manage session state and private candidate storage with Row-Level Security, and implement the evaluation engine using the Prometheus 7B v2 model on our 1-to-5 practice rubric."*

---

## 2. Interactive API Documentation & Validation (1.5 minutes)

1. **Open Swagger UI**:
   - Navigate to `http://localhost:8000/docs` in your browser.
2. **Show Defensive Validation**:
   - Point out `POST /sessions`.
   - Explain: *"We use Pydantic v2 schemas to strictly validate inputs. For CV upload, we support both `.pdf` text extraction and `.txt`. Empty files, non-PDF/TXT extensions (like `.exe`), or files exceeding 5MB are immediately rejected with clean HTTP 400 errors before touching our database."*
3. **Show Shared Contracts**:
   - Open `docs/api-contract.md`.
   - Explain: *"We established formal contracts across our team early on: Session Analysis, Question Records, Answer Evaluations, and Final Cheat Sheet Reports."*

---

## 3. Live Session Walkthrough via Swagger or Curl (2 minutes)

Demonstrate the full lifecycle in 4 simple clicks on Swagger:

1. **Create Session** (`POST /sessions`):
   - Role: `Machine Learning Engineer`
   - Job: `We need an ML Engineer with PyTorch, FAISS vector search, and LLM evaluation.`
   - CV: `3 years experience in NLP and semantic search engines.`
   - Execute -> Receive `session_id`.
2. **Retrieve the 7 Questions** (`GET /sessions/{id}/questions`):
   - Execute -> Shows the 7 distinct technical questions with `target_skill`, `difficulty`, and `reference_criteria`.
   - Explain: *"These questions are prepared specifically for this candidate based on CV gaps."*
3. **Submit Answer & Live Scoring** (`POST /sessions/{id}/answers`):
   - Submit question `q1`:
     - `original_transcript`: Raw speech from Whisper.
     - `corrected_transcript`: Candidate edited answer (`"I use IVF with Product Quantization to compress vectors into memory."`).
   - Execute -> Immediate response with **Rubric Breakdown**:
     - `correctness`: 4/5
     - `coverage`: 4/5
     - `relevance`: 5/5
     - `evidence_and_structure`: 4/5
     - `feedback`: Concrete technical improvement points.
     - Notice: *"Scores describe practice performance on this attempt, not the probability of being hired."*
4. **Generate Final Report & Download Preparation PDF** (`POST /sessions/{id}/report` and `GET /sessions/{id}/pdf`):
   - Shows cheat sheet synthesis: key strengths, priority gaps, answer structures, and direct PDF stream.

---

## 4. Scoring Calibration & Prometheus Architecture (1.5 minutes)

1. **Explain Scorer Architecture**:
   - Show `backend/app/scoring/interface.py` and `factory.py`.
   - *"Our scoring engine is completely decoupled. By setting `SCORER_BACKEND=ollama` or `mock`, we can seamlessly switch between live local Prometheus 7B v2, hosted vLLM/HuggingFace API, and a deterministic MockScorer with zero code changes."*
2. **Run Calibration Benchmark in Terminal**:
   ```bash
   .\venv\Scripts\python.exe backend/scripts/eval_scoring.py
   ```
   - Point to terminal output:
     - 15 human-annotated test cases (Weak, Partial, Strong).
     - Pearson Correlation ($r \approx 0.77$) and low Mean Absolute Error (MAE $\approx 0.93$).
   - *"We verified that our evaluation system reliably separates weak from strong answers and closely mirrors human interview benchmark ratings."*

---

## 5. Security, Row-Level Security & Privacy (1 minute)

1. **Show Supabase Schema & RLS**:
   - Open `backend/migrations/001_initial_schema.sql`.
   - Highlight: `ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;`
   - *"Candidates can only read and write their own data. Even if candidate A knows candidate B's session ID, our JWT middleware and database RLS return HTTP 403 Forbidden."*
2. **GDPR Compliance**:
   - Point out `DELETE /user/data`:
   - *"Candidates have full right to be forgotten; one call cascades and wipes all their session records, transcripts, and reports."*

---

## 6. Automated Pytest Verification (30 seconds)

Run tests in front of the jury:
```bash
.\venv\Scripts\python.exe -m pytest backend/tests/ -v
```
All **11 tests pass in ~0.3 seconds**, validating:
- File & input validation
- Security & JWT isolation
- Prometheus regex parser
- End-to-end session flow

---

## 7. Closing Statement
> *"Our backend is fully typed, tested, documented, and resilient with local SQLite and mock fallbacks so that any teammate or evaluator can run it with zero friction. I am ready for any technical questions."*

