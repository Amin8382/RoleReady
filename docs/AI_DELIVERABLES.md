# Mohamed Amin Guesmi — AI and data delivery tracker

## 1. What the current branch actually provides

- [x] Standalone Python AI package with testable modules
- [x] CSV/JSONL ingestion, deterministic duplicate-aware dataset splitting and manifest
- [x] Explicit license/provenance warnings and synthetic sample records
- [x] Dependency-free lexical retrieval baseline
- [x] Optional BGE-small-en-v1.5 / FAISS implementation; synthetic CPU/CUDA smoke passed on target machine (quality benchmark pending)
- [x] Qwen OpenAI-compatible endpoint adapter and seven-question structured output validation
- [x] Basic automated structural evaluation metrics, with hallucinated-source detection
- [x] Reviewed-only SFT data export to prepare for later fine-tuning
- [x] Human evaluation and dataset source templates
- [x] AI unit tests and GitHub CI workflow definition

## 2. Next tasks — important not to misrepresent as done

- [ ] Verify each external dataset publisher, exact URL, version, redistribution/training license and raw counts
- [ ] Curate relevant English-language software/data/AI role subsets and validate each reference answer
- [ ] Review representative question samples and create 30 *held-out* CV/job test cases
- [x] Provision local Qwen3.5 4B Q4_K_M; verify synthetic JSON/RAG generation and record VRAM/latency/errors (full RAM and held-out quality benchmarks pending)
- [ ] Evaluate three prompt variants against held-out human ratings: Qwen alone, Qwen + lexical search, Qwen + FAISS
- [ ] Add FAISS index revision/persistence strategy, privacy guardrails and embedding version to result metadata
- [ ] Create **CV/job-conditioned** instruction examples, independently review them, and train LoRA only with adequate hardware
- [ ] Compare LoRA against the strongest baseline before claiming improvement
- [ ] Supply service adapter to Oussema using shared typed contracts; Khaled wires UI through backend
- [ ] Run and investigate GitHub CI and integrated tests, and merge reviewed PRs in order

## 3. Quality protocol

For at least 30 disjoint CV/job scenarios, each reviewed by two people:
- Relevance to a given job requirement: 1–5
- Personalization to actual CV evidence: 1–5
- Technical correctness: 1–5
- Distinctness and variety across seven questions: 1–5
- Any invented CV claim: yes/no
- Latency, failure rate, model identifier, prompt version, retrieval variant

Keep weak, partial and strong **answers** as a distinct test set for Oussema's Prometheus-based rubric scoring. Do not use the same evaluation examples in retrieval or LoRA training. The human review template is in ai/evaluation/.

## 4. Next team handoff

To **Oussema**: question_id, text, target_skill, difficulty, reason_for_asking, reference_criteria, retrieved source_ids, mode, model identifier and failures. Never transmit model keys to the browser.

To **Khaled**: seven question objects and evidence-aware explanation labels; playback/transcription integration is owned by frontend/voice and exposed through backend. Display absent CV evidence neutrally rather than declaring missing skills.

## 5. Academic evidence required

Save experiment config hashes and anonymized predictions, manual evaluation sheets, source manifest/version, training hyperparameters, performance tables and final model decisions. No fine-tuning or full integration benchmark is complete in this branch.

## 6. Local runtime evidence

Mission 001 verified an isolated Python 3.11.18 environment, torch 2.11.0+cu128
GPU acceleration, all 17 existing AI tests, and real BGE/FAISS, Whisper Small
English and Kokoro CPU/GPU inference. Exact revisions, timings, GPU memory,
installation issues and the Windows dependency snapshot are documented in
[the local environment report](../ai/docs/LOCAL_ENVIRONMENT_2026-11-09.md).
At the Mission 001 snapshot, Qwen/Prometheus weights, live endpoints, held-out
quality evaluation and product integration remained pending. The nested local clone and original environment
were preserved.

Mission 002 adds actual local Qwen Q4_K_M inference through Ollama, 98 passing AI
tests and six successful synthetic seven-question generation cases across lexical
and BGE/FAISS retrieval. Exact artifacts, runtime measurements, earlier rejected
runs and unedited samples are linked from [the Mission 002 report](../ai/docs/MISSION_002_QWEN_RAG.md).
The samples carry explicit quality findings; no generated criteria are approved
as reviewed scoring references. Prometheus, independent human evaluation and
end-to-end product integration remain pending.

Final Mission 002 validation records 6/6 structural cases and all 42 question reviews, with an explicitly open qualitative gate for technical criteria, citation alignment and fairness findings. Do not treat structural success as full mission-quality approval.
