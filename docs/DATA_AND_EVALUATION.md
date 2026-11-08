# Data and experiments

## Current corpus

| Source | Unique records | Use |
| --- | ---: | --- |
| InterviewForge | 20,444 | Synthetic question examples; only its 16,299 training-split rows enter retrieval |
| raghu298 ML interview SFT | 531 | Supplemental reference candidate; 35 duplicate question rows removed; excluded from retrieval pending provenance review |
| ML systems interview benchmark | 30 | Evaluation only; references, concepts and rubric retained |

`configs/datasets.json` pins the source revisions, filenames, checksums and intended use. Source licence metadata is not proof of upstream ownership. No source is marked human-reviewed. InterviewForge has no answer column, despite wording in its card. These are not paired CV/job-to-seven-question fine-tuning examples.

The pipeline validates hashes before parsing, normalizes exact duplicate questions, isolates external evaluation records and assigns deterministic 80/10/10 splits from question hashes. This prevents exact duplicate leakage but **does not** prove absence of paraphrase, template-family or semantic leakage. Review and group related items before training/evaluation claims.

Run `uv run --no-sync dvc repro`. DVC stages download, prepare, embed/index and compare retrieval. Git keeps `dvc.lock` and small metric reports; DVC keeps raw/processed data and the index. Rejected checksum inputs never silently enter the bank.

## Measured retrieval smoke

Eight assistant-authored paraphrases have provisional relevant IDs in `data/benchmark/retrieval_queries.json`. The labels are incomplete: other retrieved questions may also be relevant. They are useful for regression smoke checks and are not evidence that the product is accurate on arbitrary interviews.

| Retriever | Hit@5 | MRR@5 | nDCG@5 |
| --- | ---: | ---: | ---: |
| TF-IDF | 0.750 | 0.604 | 0.641 |
| BGE-small-en-v1.5 | 1.000 | 1.000 | 1.000 |

See `reports/retrieval_comparison.json` and per-query reports. BGE average latency includes its initial model loading, so it must not be interpreted as steady-state service latency. Measure warm/cold latency separately before setting a product target.

## Next evaluation work

1. Each teammate reviews a share of the corpus and contributes relevance judgments for realistic role/CV queries, including mismatches and hard negatives. Keep the benchmark frozen while comparing retrievers.
2. Create synthetic or explicitly consented/redacted CV/job cases spanning junior, mid and senior roles. Two teammates score relevance, coverage, factual support and question diversity independently.
3. Calibrate Prometheus using reviewed strong/partial/weak answers. Report agreement with human scores, mean absolute error, refusal/error rates, and examples where feedback is misleading. The reference answer is guidance, not a single required answer.
4. Measure English transcription on real accents and technical terms with consent. Report WER plus a separate count of consequential technical errors. A Kokoro-to-Whisper sentence is only a connectivity smoke test.
5. Compare an unchanged Qwen baseline against any future adapter on held-out candidate/job/template groups. Record hardware, precision, token limits, dataset hash and prompt version.

## Fine-tuning gate

No custom RoleReady adapter has been trained. Before a LoRA run, prepare reviewed input/output pairs with `candidate_group_id`, `job_group_id`, `question_family_id`, CV, JD, level and the complete validated output schema. Partition connected groups so that shared candidate/job/family examples cannot cross train/validation/test. Mask input tokens in the supervised loss and train only on target output tokens. Never use the 30-question external benchmark as training material.

Qwen3.5 includes a vision component even though this product uses text; use its supported model class/training recipe and target only appropriate language modules. A generic unverified `AutoModelForCausalLM` script is not provided as a tested training solution. The first training milestone requires a compatible GPU environment, reviewed pairs and a successful small-batch smoke run before a full job.

The existing English fine-tuned T5 question generator remains a comparison baseline: prior outputs showed role drift/repetition. DistilGPT2 was not selected because of poor interview wording. Original outputs and limitations remain in `docs/research/`.
