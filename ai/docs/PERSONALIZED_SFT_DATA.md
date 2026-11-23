# Personalized question-generation SFT pilot

This workflow prepares data for the future original/fine-tuned × no-RAG/RAG
comparison. It does not train a model, certify question quality, or approve
Prometheus scoring references. Existing evaluation inputs and predictions are
excluded, not recycled as training pairs. The original Mission 003 code and
freeze remain unchanged; new preparation code lives in `roleready_training/`.

## Dataset design

The user selected 256 new fictional CV/job scenarios. There are eight priority
roles, four experience levels and eight authored project families per role.
All experience-level variants of a project stay together. A fixed seed assigns
six project families per role to training, one to validation and one to test:
**192 train / 32 validation / 32 test**. This is a pilot, not evidence that the
sample is large or diverse enough for useful fine-tuning.

Inputs and targets serve the actual task: CV + job + role/level → seven
personalized questions. They do not teach the model to answer interview questions.
InterviewForge has no reference-answer column; none is invented here. Its corpus
remains retrieval-only, the SFT source stays quarantined, and ML Systems Bench
remains excluded from training. No real candidate profiles are used.

The existing local Qwen model drafts targets with an empty retriever. No corpus
IDs or retrieved passages enter those requests. Every request/response is
preserved, including rejected attempts. Draft criteria remain unreviewed.
Only the clean first prompt is used for SFT export, never retry instructions.
Outputs retain the exact current inference schema, with no extra question-ID key.
Stable question IDs are assigned by the serving pipeline after generation.

The exclusion registry covers the old demonstration CV/job inputs, all 32 frozen
ablation inputs, retrieval queries, parsed accepted/rejected ablation questions,
the separate ML Systems benchmark and public demonstration question samples.
Exact and near input matches are rejected. Complete targets cannot duplicate
across supervised partitions. Hash checks do not prove zero semantic overlap;
reviewers must inspect near paraphrases and generic duplicated material.

## Local generation and review

From `ai/`, use the preserved inference environment and existing cached model:

```powershell
$env:HF_HOME = "$PWD/.runtime/huggingface"
$env:HF_HUB_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
.venv311/Scripts/python.exe -m roleready_training.data prepare
.venv311/Scripts/python.exe -m roleready_training.data generate
.venv311/Scripts/python.exe -m roleready_training.data status
```

Default destination: `data/fine_tuning/personalized-v1/`, ignored by Git.
`manifest.json` binds scenario/exclusion hashes, code versions and teacher identity.
`scenarios.jsonl` holds partitioned inputs; `drafts/` preserves request journals
and targets. `status.json` reports progress and keeps `ready_for_training=false`.
On completion, `review-pack/` contains all 256 inputs/targets plus two pending
review files; `completion.json` records the actual generation outcome. A failed
or rejected draft needs human correction, not automatic approval or selective reruns.

The generator skips existing final records. If interrupted, first verify the PID
in `runner.lock` is dead before removing only that stale lock; an uncertain request
is recorded as interrupted on resume. Never delete or overwrite prior outputs.
Only the already provisioned local model is used; no weights are downloaded.

To create an earlier immutable review snapshot while drafts are still running:

```powershell
.venv311/Scripts/python.exe -m roleready_training.data review-pack --out data/private/sft-review-initial
```

Human editors may fix or author targets in a COPY of `targets.jsonl`; version the
edits. Keep the input unchanged. Both reviewers independently check job relevance,
CV personalization, technical correctness (including criteria), diversity,
difficulty and unsupported assumptions. Approval requires every check true,
`status=human_approved`, a real reviewer identifier and review date. Agent comments
or structural passes are not human approvals. Identities are declared rather
than authenticated; do not invent them to satisfy the gate.

`approval_sha256` is the canonical digest of `{"input": input, "target": target}`
using `roleready_ai.tracking.digest`. Recompute it after a human edit and have BOTH
reviewers approve that exact new hash. Old approvals become stale. Example command
for a reviewed target row, without assigning any human approval automatically:

```python
from roleready_ai.tracking import digest
approval_hash = digest({"input": row["input"], "target": row["target"]})
```

The exporter requires all 256 targets to be structurally valid, leak-checked and
approved by two distinct people. It writes a new immutable release:

```powershell
.venv311/Scripts/python.exe -m roleready_training.data export --targets data/private/reviewed/targets.jsonl --reviews data/private/reviewed/reviewer-1.jsonl data/private/reviewed/reviewer-2.jsonl --out data/fine_tuning/personalized-approved-v1
```

The release contains chat-message JSONL for train/validation/test and a manifest
with data/review hashes and counts. Train ONLY on `train.jsonl`; choose training
settings using validation, preserve test for independent assessment. The original
32-case ablation stays outside every supervised partition and remains the common
comparison set for original/fine-tuned models. Question-target review does not
authorize future interview-answer scoring.

## MLOps and readiness

Generation completion logs dataset counts and hashes to the local
`roleready-sft-data` MLflow experiment. It records unreviewed status, not fabricated
quality metrics. No data is uploaded to cloud storage. Keep private review files
and raw draft outputs out of Git. Once the dataset version is complete, snapshot
it locally with the existing isolated DVC tool and retain the resulting pointer
locally; no remote data push is configured or implied.

For an unattended local snapshot after generation, run (from `ai/`):

```powershell
.venv311/Scripts/python.exe scripts/snapshot-sft-data.py --dataset data/fine_tuning/personalized-v1
```

This waits for completion and lock release, runs only local `dvc add`, and saves
the pointer SHA-256 in `.runtime/training-data/dvc-snapshot.json`. It does not
change any review status. Keep the generated `.dvc` pointer locally with the
snapshot; no push to a DVC remote occurs.

Data generation is not fine-tuning readiness: reviewed targets, model-training
runtime/hardware checks and a frozen training/comparison protocol are still
required before a training run. The existing quantized inference service remains
unchanged. Never claim improvement from self-generated targets without independent
held-out evaluation.
