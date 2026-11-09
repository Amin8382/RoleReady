# RoleReady API Contract & Shared Data Models

**Authors:** Oussema Ferchichi (Backend & Scoring Lead), Mohamed Amin Guesmi (AI & Data Pipeline), Khaled Briki (Frontend & Voice)  
**Version:** 1.0.0  
**Updated:** 2026-11-09  

---

## 1. Overview & Architectural Boundaries

RoleReady coordinates three main modules through clear, typed contracts:
1. **Frontend (Khaled)**: Next.js/React communicates via standard JSON REST endpoints and multipart form uploads.
2. **AI & Data Pipeline (Amin)**: FAISS retriever + Qwen 3.5 4B CV/job analysis and question selection.
3. **Backend & Evaluator (Oussema)**: FastAPI server, Supabase/SQLite persistence, JWT access control, and Prometheus 7B v2 scoring engine.

> **Ethical Calibration Principle**: All evaluation endpoints output **practice performance scores (1–5 scale)**. Scores **never** represent hiring probability or job candidacy fitness.

---

## 2. Shared Data Records

### 2.1 Session & Analysis Record
Passed when initiating a session and after CV-to-job matching:
```json
{
  "session_id": "sess_9fa2718e",
  "target_role": "Machine Learning Engineer",
  "experience_level": "mid",
  "cv_text": "Jane Doe - 3 years experience building NLP search engines...",
  "job_text": "We are seeking a Machine Learning Engineer with experience in PyTorch, FAISS...",
  "strengths": [
    "Demonstrated hands-on experience with vector embeddings and PyTorch models",
    "Strong Python software engineering practices"
  ],
  "requirements_not_evidenced": [
    "FAISS deployment at 10M+ scale (Note: missing CV evidence does not prove a missing skill)"
  ],
  "supporting_source_excerpts": [
    "CV: Built semantic search indexing 50,000 documents using BERT embeddings",
    "Job: Must optimize latency and memory for 10M vector catalogs"
  ]
}
```

### 2.2 Question Record
Passed for each of the 7 distinct interview questions:
```json
{
  "question_id": "q1",
  "text": "How would you handle approximate nearest neighbor indexing when scaling to 10 million vectors?",
  "target_skill": "Vector Search & FAISS",
  "difficulty": "medium",
  "reason_for_asking": "Target job requires FAISS deployment at scale; CV highlights small-scale embeddings only.",
  "reference_criteria": "Mentions IVF/HNSW indexing trade-offs, quantisation (PQ), memory footprint, and latency vs recall balance.",
  "source_ids": ["ML_interview_bench_04"]
}
```

### 2.3 Answer & Evaluation Record
Passed upon answer submission and evaluated by Prometheus 7B:
```json
{
  "session_id": "sess_9fa2718e",
  "question_id": "q1",
  "original_transcript": "I would use inverted file index and product quantize...",
  "corrected_transcript": "I would use an inverted file index (IVF) combined with product quantization (PQ) to compress vectors into RAM.",
  "rubric_version": "v1.0",
  "scores": {
    "correctness": 4,
    "coverage": 4,
    "relevance": 5,
    "evidence_and_structure": 4,
    "overall_score": 4.25
  },
  "evidence": [
    "Identified IVF and Product Quantization (PQ) directly",
    "Addressed RAM constraints as required by high-volume scale"
  ],
  "feedback": "Strong answer. To reach a score of 5, explicitly contrast IVF search latency with graph-based HNSW recall.",
  "practice_notice": "Scores describe practice performance on this attempt, not the probability of being hired."
}
```

### 2.4 Final Report & Cheat Sheet Record
Aggregated session summary and downloadable cheat sheet payload:
```json
{
  "session_id": "sess_9fa2718e",
  "target_role": "Machine Learning Engineer",
  "experience_level": "mid",
  "seven_results": [ "/* 7 AnswerEvaluation objects */" ],
  "average_session_score": 4.1,
  "priority_improvements": [
    {
      "category": "System Architecture Trade-offs",
      "gap_description": "Tendency to pick one algorithm without contrasting against alternative trade-offs.",
      "action_item": "Practice stating memory vs latency trade-offs for indexing schemes."
    }
  ],
  "cheat_sheet_content": {
    "key_strengths_summary": ["High technical accuracy on core NLP concepts"],
    "priority_improvements": [ "/* list of priority gaps */" ],
    "key_technical_concepts": ["FAISS IVF-PQ", "HNSW graph traversal", "Cross-Encoder Re-ranking"],
    "recommended_answer_structures": ["State trade-off -> Propose primary technique -> Benchmark metric"],
    "suggested_next_practice_steps": ["Review large-scale vector quantization math", "Re-attempt questions 3 and 5"]
  },
  "pdf_location": "/sessions/sess_9fa2718e/download-pdf",
  "practice_notice": "Scores describe practice performance, not the probability of being hired."
}
```

---

## 3. Endpoints Specification

| Method | Path | Summary | Auth Required |
|---|---|---|---|
| `POST` | `/sessions` | Create interview session (multipart form or JSON, supports PDF/text upload) | Optional (anonymous/demo allowed) |
| `GET` | `/sessions/{id}` | Retrieve session state & completion status | Yes (RLS owner or public demo) |
| `POST` | `/sessions/{id}/analysis` | Store CV vs Job alignment analysis (from Amin's pipeline) | Yes |
| `GET` | `/sessions/{id}/questions` | Retrieve the 7 session questions (or triggers generation if absent) | Yes |
| `POST` | `/sessions/{id}/questions` | Store or update the 7 questions | Yes |
| `POST` | `/sessions/{id}/answers` | Submit answer (Whisper raw + user edited), triggers Prometheus scoring | Yes |
| `GET` | `/sessions/{id}/results` | Retrieve all scored answers for this session | Yes |
| `POST` | `/sessions/{id}/report` | Finalize session, build summary cheat sheet, generate PDF | Yes |
| `GET` | `/sessions/{id}/pdf` | Stream/download the preparation cheat sheet PDF | Yes |
| `DELETE` | `/user/data` | GDPR/Privacy: Delete all sessions, transcripts, and CVs for the authenticated user | Yes |
| `POST` | `/stt/transcribe` | Adapter for Khaled: Audio file -> Whisper small transcript | No (or bearer) |
| `POST` | `/tts/speak` | Adapter for Khaled: Question text -> Kokoro 82M audio | No (or bearer) |

---

## 4. Error Handling & HTTP Status Codes

- `400 Bad Request`: Empty file, unsupported file extension (only `.pdf` or `.txt` allowed), or file size > 5 MB.
- `401 Unauthorized`: Missing or invalid Bearer JWT when `AUTH_ENFORCE_JWT=true`.
- `403 Forbidden`: Attempting to access another user's session ID.
- `404 Not Found`: Session or question does not exist.
- `422 Unprocessable Entity`: Pydantic payload validation error.
- `503 Service Unavailable`: Upstream model timeout or failure (Prometheus/Whisper), with actionable error message and retry prompt.

