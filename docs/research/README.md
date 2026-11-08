# RoleReady: model and data selection

Research date: 7 November 2026. Scope: English interview preparation, CV + target job, personalized questions, voice practice, feedback, and a final preparation sheet. The public datasets found are strongest for software, data, AI, and adjacent technical roles. They do not establish coverage of every profession.

## Recommendation

Use `Qwen/Qwen3.5-4B` as the **candidate backbone** for CV/JD analysis, personalized question generation, and the final preparation sheet. Start with retrieval and explicit prompts, then compare a RoleReady LoRA against the unchanged backbone on held-out CV/JD pairs. This is an engineering recommendation, not a measured win: Qwen was not run in this investigation, and no RoleReady fine-tune has been trained.

Use `prometheus-eval/prometheus-7b-v2.0` as the **candidate specialized evaluator**. It is fine-tuned for rubric-based evaluation and supports scored feedback. Its original evaluation task concerns model responses; transfer to human interview answers must be tested against human ratings.

The closest small ready-made question generator found is `sudaisdev/Question_Generation_model`. Keep it as an inexpensive experimental baseline. Direct testing found both useful and problematic questions. It is not yet a dependable replacement for the full personalized workflow.

## Proposed model lineup

| Component | Candidate | Evidence and limitation |
|---|---|---|
| Analysis, questions, cheat sheet | [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) | Official post-trained model, Apache-2.0 metadata. Use text inputs and direct-response mode. Not an interview-specific fine-tune; not tested here. |
| Evaluation | [Prometheus 7B v2](https://huggingface.co/prometheus-eval/prometheus-7b-v2.0) | English evaluator fine-tuned using feedback/preferences. Input includes task, candidate answer, reference answer, and rubric. No RoleReady calibration yet. |
| Retrieval | [BGE-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) | English embeddings, 384 dimensions, 512-token input limit, MIT metadata. Use one short question/reference record per indexed unit. Rebuild embeddings if replacing the current embedding model. |
| Transcription | [Whisper-small.en](https://huggingface.co/openai/whisper-small.en) | English ASR checkpoint, 244M parameters. Evaluate on the team's actual accents and technical vocabulary. |
| Spoken questions | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Open-weight TTS, Apache-2.0 metadata. English voice generation; no cloning or retraining needed for the prototype. |

These are five distinct models with distinct responsibilities. FAISS is an index, not a sixth model. The proposal does not require paying for inference APIs, but local compute and hosting still have costs. Hardware has not been supplied. The 4B/7B models need a separate quantized-inference check on the team's machine; CPU latency may be unsuitable for live practice. Raw 4-bit parameter storage is roughly parameters/2 bytes, before quantization metadata, runtime, activations, and KV cache. This is not a RAM/VRAM fit guarantee. Load large components sequentially when memory is constrained.

## Ready-made interview models examined

| Model | Decision | Reason |
|---|---|---|
| [sudaisdev/Question_Generation_model](https://huggingface.co/sudaisdev/Question_Generation_model) | Keep as baseline | English job-details-to-question model; short 512-token input; published prompt has no explicit CV field. Eight synthetic cases produced useful outputs but also role drift and redundant wording. No published held-out personalization benchmark found in the card. |
| [Zeeshan506/echohire-qgen-distilgpt2](https://huggingface.co/Zeeshan506/echohire-qgen-distilgpt2) | Do not select as main generator | Small model with title/skill inputs. Exploratory outputs included invented technical concepts and repetitive wording. |
| [ocbyram/Interview_Prep_Help](https://huggingface.co/ocbyram/Interview_Prep_Help) | Secondary comparison | Directly relevant CV/JD task, based on Qwen2.5-7B. Author's reported task BERTScore F1 is 0.830 versus 0.841 for its base model; this does not demonstrate a fine-tuning improvement. GPL-3.0 metadata. |
| [shimogerald/lora_interview_coach](https://huggingface.co/shimogerald/lora_interview_coach) | Reference-answer experiment | Primarily trained to answer software-engineering interview questions, not to produce CV-specific questions or calibrated grades. Adapter also requires its base model. |
| [beratdgan/Qwen3-14B-Interview-Coach](https://huggingface.co/beratdgan/Qwen3-14B-Interview-Coach) | Not the default | Primarily creates answer rubrics; larger 14B model and CC-BY-NC-4.0 metadata. |
| [CodeSlayer/finetuned-feedback-model](https://huggingface.co/CodeSlayer/finetuned-feedback-model) | Not the default | Access is gated. Limited published evaluation detail. Tone/emotion heuristics do not establish answer correctness. |
| [AI-Mock-Interviewer/T5](https://huggingface.co/AI-Mock-Interviewer/T5) | Not immediately usable | API reports manual gating; adapter for FLAN-T5-large. |
| [raghu298/ml-interview-coach-qwen3-4b-sft](https://huggingface.co/raghu298/ml-interview-coach-qwen3-4b-sft) | Do not choose from the name alone | No model card when inspected. Linked training dataset teaches answering; no verified personalization or scoring evidence. |

Repository labels are recorded as publisher metadata, not a legal clearance of all upstream source material. A small adapter download is not the total memory or download requirement.

## What the direct generation check found

`smoke_results.jsonl` contains every prompt, model revision, decoding setting, output, and runtime. `smoke_cases.json` contains eight entirely synthetic technical-role cases. T5 used all eight distinct inputs. The documented DistilGPT-2 input only accepts title and skills, so three backend cases collapse to the same prompt: there are six distinct DistilGPT-2 prompts and eight calls. Do not treat their repeated outputs as three independent failures.

This is an exploratory functionality check, not a representative or blinded benchmark. It does not test real CV personalization, all job families, scoring, or the complete application. The models use different published input formats and decoding strategies, so runtimes are not a fair speed comparison. Outputs were capped at 128 new tokens; truncation of a multi-question list is not, by itself, a model-quality failure.

- T5 produced a relevant accessibility question and a relevant database-latency scenario.
- For a backend role it also generated a frontend debugging question.
- Its data-analyst question made a redundant and unclear comparison involving real-time and dynamic sales data.
- DistilGPT-2 produced a comparison involving a purported "slowAPI database", plus other category-confused technical wording.

The environment initially used Transformers 4.57.6, which could not read the T5 tokenizer metadata. The successful run used Transformers 5.16.1, matching the checkpoint's saved version. A warning reported distinct shared/LM-head weights despite the tie flag; the loader preserved them as distinct. The repository files were not edited. HF metadata counted 247,577,856 T5 checkpoint parameters versus the card's approximate 220M; use the actual files for resource planning.

## Dataset audit and selection

Audits read full files at pinned revisions. Duplicate questions are defined as `" ".join(question.casefold().split())`; punctuation is retained. Counts measure extra rows beyond unique questions, not duplicate groups. These are structural checks, not a technical correctness or near-duplicate audit.

| Dataset | Verified contents | Proposed use |
|---|---|---|
| [Davichick/InterviewForge_GenDS](https://huggingface.co/datasets/Davichick/InterviewForge_GenDS) | 20,444 rows; 38 role labels; synthetic; MIT metadata. No answer column in the downloaded CSV, although the card describes one. No exact normalized duplicate questions found. | Primary question-bank candidate after relevance/quality review. Not answer-grading truth. |
| [raghu298/ml-interview-sft-dataset](https://huggingface.co/datasets/raghu298/ml-interview-sft-dataset) | 566 Q&A rows; 35 repeated-question rows; 531 unique normalized questions. No empty answers. Apache-2.0 metadata; several upstream sources are document filenames, with provenance needing review. | Supplemental ML/AI reference material after deduplication and expert checking. Not scored human answers. |
| [Max00035/ml-systems-interview-bench](https://huggingface.co/datasets/Max00035/ml-systems-interview-bench) | 30 questions with reference answers, expected concepts, and rubric anchors. Apache-2.0 metadata. No exact question duplicates. | Small starting point for a human-rated evaluation set. Too small to establish overall reliability. |
| [juasdexter/interview_questions](https://huggingface.co/datasets/juasdexter/interview_questions) | 602 rows; 158 repeated-question rows; 6 empty answers. Java 496, PHP 52, Magento 54. Apache-2.0 metadata. | Optional niche supplement after cleaning; not a broad primary corpus. |
| [AI-Mock-Interviewer/Train_data](https://huggingface.co/datasets/AI-Mock-Interviewer/Train_data) and [Test_Data](https://huggingface.co/datasets/AI-Mock-Interviewer/Test_Data) | 6,932 train and 771 validation rows. 626/12 repeated-question rows respectively. 126 unique normalized questions appear in both. Apache-2.0 metadata; underlying provenance not documented. | Role-to-question examples only. Do not trust the supplied split for a leakage-free benchmark. |

[anuj6316/Interview_Questions](https://huggingface.co/datasets/anuj6316/Interview_Questions) looked relevant in search results, but both the direct page and API returned HTTP 401. It is not included as an accessible dependency.

[Prometheus Feedback-Collection](https://huggingface.co/datasets/prometheus-eval/Feedback-Collection) is another source for general rubric/feedback formatting: 100k synthetic examples, CC-BY-4.0 metadata. It is not interview-domain ground truth and is not an independent test set for Prometheus. It was reviewed via its card/viewer, not downloaded or audited here.

## The data that still needs to be built for RoleReady

A question bank is not the same as a CV-conditioned training set. To teach personalization, create reviewed examples with:

```text
candidate_profile + job_description + target_skill + difficulty
    -> interview_question + reason_for_asking + supporting_CV/JD_spans
```

To calibrate evaluation, use:

```text
question + candidate_answer + reference_criteria
    -> human_scores + cited_answer_evidence + actionable_feedback
```

Use the candidate-supplied job description as the primary session target. A large scraped job-board corpus is not required for the first version. Start evaluation with consenting/anonymized or synthetic CV/JD pairs. Distinguish a skill not evidenced in the CV from a skill the person actually lacks. Behavioral answer examples must not invent the candidate's achievements.

Generate any synthetic additions as drafts, retain their origin, and review them. Split by candidate, job, and question family; deduplicate before splitting. Keep final evaluation questions and answer variants out of training and the runtime retrieval corpus. For retrieval evaluation, separately define an allowed corpus and human relevance labels; do not count a retrieved exact gold answer as independent evaluation evidence.

## Concrete next experiment

1. Choose an initial role scope and review a manageable question-bank subset.
2. Create 30 held-out CV/JD cases spanning junior and experienced candidates; use two reviewers to assess personalization, relevance, correctness, diversity, and unsupported assumptions.
3. Compare T5, Qwen with prompts only, and Qwen with retrieval. Log latency, memory, and repeated questions. These experiments have not yet been run.
4. Fine-tune Qwen using LoRA only after the paired training examples are ready. Compare against the unchanged model using the same held-out cases.
5. Create at least three answer variants per evaluation question (weak, partial, strong) and have reviewers score them independently. Calibrate Prometheus on rubric adherence and agreement; do not grade by embedding similarity alone.
6. Test Whisper on real English interview audio with technical vocabulary, and assess Kokoro intelligibility/latency. Add a transcript correction step before grading when recognition is uncertain.

Suggested grading dimensions are correctness, coverage, relevance, and evidence/structure. Accent, inferred emotions, and personality are not proxies for technical competence. Scores are practice feedback, not hiring predictions.

## Reproduce and inspect

`audit_datasets.py` downloads only the six audited source files at their pinned revisions, computes counts, then writes `dataset_audit_reproduced.json`. It does not train a model or upload anything. Python's standard library is sufficient.

```bash
python audit_datasets.py
```

`smoke_test.py` downloads the two model checkpoints (about 1.32 GB of model weights total) and runs locally on CPU. The complete successful dependency snapshot is in `tested_environment.txt`. Use an isolated Python 3.12 environment. The run used CPU PyTorch; choose the appropriate PyTorch build for your platform. Model weights and third-party raw datasets are not included in this package.

```bash
python -m venv .venv
# Activate the environment for your operating system.
python -m pip install -r tested_environment.txt
python smoke_test.py
```

If the platform's default package index cannot resolve the CPU-specific PyTorch build in the snapshot, install that build from the official PyTorch CPU index before installing the remaining packages. Minor timing/output differences across systems are possible.

## Research reference

[Prometheus 2 paper, EMNLP 2024](https://arxiv.org/abs/2405.01535) provides evaluation research for the evaluator. Published results concern the paper's benchmarks, not RoleReady. All other primary model and dataset sources are linked above. No application integration, Qwen/Prometheus inference, training, or production deployment was completed in this research pass.
