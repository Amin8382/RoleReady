# RoleReady — team implementation agreement

This plan follows the uploaded *RoleReady Project Overview* (8 November 2026), without claiming model integrations already exist.

## Scope

English-only interview preparation for software, data and AI roles. Candidate uploads a CV and a job description, chooses a target role and experience level; the product performs evidence-aware analysis, generates **seven distinct questions**, supports spoken practice with an editable transcript, scores answers using a versioned rubric, and exports a PDF preparation sheet.

## Owners and interface boundaries

| Owner | Module | Handover |
| --- | --- | --- |
| Mohamed Amin Guesmi | AI & data | Curated datasets, audited manifest, embeddings/FAISS retriever, Qwen analysis and question-generation adapter, reference criteria, LoRA comparison, evaluation results |
| Oussema Ferchichi | Backend & evaluation | FastAPI contracts, session persistence, Supabase security, Prometheus rubric evaluator, error handling, scoring calibration |
| Khaled Briki | Frontend & voice | Next.js interface, question narration, microphone recording, editable Whisper transcript, saved sessions, feedback and PDF download |

Coordinate through a single repository with reviewed small branches. The model APIs and secrets live on the server.

## Shared records

- `SessionRequest`: `target_role`, `experience_level` (`entry`/`junior`/`mid`/`senior`), `cv_text`, `job_description`.
- `SessionResponse`: `session_id`, role/level, `analysis` with evidenced strengths and requirements not evidenced, `questions` (seven expected), and `mode`.
- `InterviewQuestion`: `question_id`, `text`, `target_skill`, `difficulty`, `reason_for_asking`, `reference_criteria`, `source_ids`. Empty `source_ids` mean no retrieved source, NOT grounded RAG.
- `AnswerEvaluationRequest`: `session_id`, `question_id`, `question_text`, `original_transcript`, `corrected_transcript`, `reference_criteria`, `rubric_version`.
- **Future** `AnswerEvaluationResponse`: question identifier, four 1–5 rubric dimensions, calibrated aggregate, answer evidence, strengths, weaknesses, targeted suggestions, version/model ID, and clear limitations.

**Do not conflate missing CV evidence with missing candidate skill.** Do not treat keyword overlap or rule-of-thumb scores as validated AI assessments.

## Candidate model boundaries

- **Qwen3.5 4B**: CV/job analysis, personalized questions, final report text.
- **Prometheus 7B v2**: separate rubric-based answer evaluation. Calibrate against human ratings; no score if not configured.
- **BGE-small-en-v1.5** + **FAISS**: embedding model and vector index; FAISS is **not** a model.
- **Whisper small English**: English speech transcription; user may correct transcript before scoring.
- **Kokoro 82M**: English narration.

Candidate models have not yet been benchmarked on the target hardware. Measure latency, model RAM/VRAM, factuality, model version, and failure modes. Use sequential loading if hardware requires.

## Proposed data & quality gates

- InterviewForge GenDS: synthetic interview-question records (research overview reports 20,444 / 38 role labels), review before use.
- ML interview SFT dataset: overview reports 566 rows / 531 unique normalized questions, inspect answer quality and provenance.
- ML systems interview bench: overview reports 30 question/reference/rubric items, add independently reviewed evaluation cases.

Track source links, snapshots, licenses, deduplication, data transformations, and train/evaluation separation in a manifest. The reported counts above have **not** been independently revalidated in this code branch.

For scoring, human reviewers rate **correctness, coverage, relevance, evidence/structure** (1–5), adjusted by question type. Record disagreements, compare Prometheus to reviewer judgments, and do not misrepresent the score as hiring probability. Evaluate questions on 30 held-out CV/job cases with two reviewers. Never invent CV facts.

## Phases and gates

1. **Prepare:** lock contracts and rubric; clean small dataset sample; create held-out cases; team can run shared API.
2. **Connect text:** live Qwen + retrieval + Prometheus for seven typed answers; log model IDs, prompts, latency, failures.
3. **Complete experience:** spoken questions, recording, correction, private sessions, authentication and PDF export.
4. **Evaluate:** compare baselines, fine-tune LoRA only when review data support it, verify ratings, accent handling, provenance, privacy, and demonstration.

Current backend is **Phase 1 baseline**. `POST /api/v1/sessions` produces seven deterministic questions with no RAG sources and transparent keyword evidence. `POST /api/v1/evaluations` intentionally responds HTTP 501 until a real evaluator is integrated. The frontend still operates in its separate local demo flow; wiring it to FastAPI remains work.
