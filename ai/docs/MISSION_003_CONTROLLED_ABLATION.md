# Mission 003 continuation: controlled RAG ablation

This protocol continues commit `d304d4c`, preserving the 16,466-question public
InterviewForge corpus and existing exact BGE/FAISS index. ML Interview SFT stays
quarantined and ML Systems Bench stays outside retrieval and supervised training.
No model provisioning, answer invention, Prometheus inference or fine-tuning is
part of this stage. The original nine cases remain exploratory evidence.

## Frozen design

`evaluation/ablation/scenarios.json` contains 32 new, explicitly assistant-authored
synthetic scenarios: eight priority roles crossed with entry/junior/mid/senior.
They are disjoint from Mission 002 and Mission 003 demonstration inputs. They are
purposive examples, not a population-representative or prospectively powered study.
The protocol, rubric and scenarios must be committed before held-out generation.
Do not tune prompts using their outputs. Changes require a new disclosed freeze.

Each scenario runs with seeds 17/29/43 and three conditions: empty retrieval,
lexical top-five and persisted BGE/FAISS top-five. This is 288 generation sets
(up to 2,016 accepted questions). Six condition orders occur 16 times each across
96 scenario/seed blocks, shuffled using seed 20261122. All arms use the existing
prompt and validation policy. The evidence/citation schema resolves per input;
its concrete hash is recorded separately from the common schema-template hash.

The existing local Qwen Q4_K_M digest is required. Settings remain temperature
0.2, top-p 0.95, serving top-k 20, presence penalty 1.5, context 8192, maximum
output 4096, reasoning none, timeout 600 seconds, at most two attempts. A trial
seed is passed identically to the three arms. Seed reproducibility is not a
promise of byte-identical GPU output. Confirm seed handling using development
inputs before freezing; `freeze --unseeded` explicitly records unsupported seeds
while retaining three repetitions. Never silently downgrade a frozen protocol.

The no-RAG arm uses `EmptyRetriever`, no question examples and empty source IDs.
Every request is checkpointed before sending; response bytes are preserved as
base64 before strict validation. The capture is bounded at 2,000,001 bytes and
explicitly flagged when potentially truncated. Rejected content is not repaired.
All actual requests and retry costs count, including rejected responses. Missing
token usage is null. Compatible API timings cannot independently prove absence
of server-side context truncation; that limitation is recorded per case.

Resume skips completed cases. An unfinished request is marked interrupted rather
than resampled; its cost may remain unknown. A stale `runner.lock` requires an
operator to verify the recorded process is dead before removing that exact file.
Never delete experiment directories or rerun cases to cherry-pick successful output.

## MLflow and local privacy

The tracking server uses SQLite and proxied artifacts below `ai/.runtime/mlflow/`.
It binds only to 127.0.0.1:5000. Inference communicates through a standard-library
REST client, so the verified CUDA/voice environment gains no packages. Server
dependencies belong only in `.runtime/mlflow-env`. Tracking databases, request
journals, review identities and generated outputs are ignored by Git.

`roleready-generation` contains a protocol parent and case runs; historic cases
carry `evidence_class=exploratory`. `roleready-retrieval` records the separate
ranking benchmark and later approved judgments. Record Git commit, DVC lock hash
and artifact identifiers, corpus/index/evaluation hashes, model digest and
quantization, BGE revision, server version/settings, strategy/top-k, prompt/schema
hashes, requests/retries, tokens, latency and structural results. Unknown quality
is explicit null in artifacts and omitted from numeric MLflow metrics, with a
pending-review tag. An absent metric is not zero. Do not enable automatic tracing
or send candidate content, hidden tests or artifacts to external services.

MLflow outages do not discard inference: immutable local records can be uploaded
with `sync`. Content-derived run keys make import/synchronization idempotent.
Full original request/response journals remain local and can be audited separately.

## PowerShell commands

From the outer repository root, provision only the isolated tracking environment:

```powershell
ai/.venv311/Scripts/python.exe -m venv ai/.runtime/mlflow-env
ai/.runtime/mlflow-env/Scripts/python.exe -m pip install -r ai/requirements-mlflow.txt
ai/.runtime/mlflow-env/Scripts/python.exe -m pip check
ai/.runtime/mlflow-env/Scripts/python.exe ai/scripts/mlflow-local.py start
ai/.runtime/mlflow-env/Scripts/python.exe ai/scripts/mlflow-local.py health
```

Dashboard: http://127.0.0.1:5000. Stop only the recorded project process with
`mlflow-local.py stop`. With the experiment idle, create a new local backup using
`mlflow-local.py backup --out ai/.runtime/mlflow-backup-001`; retain the database
and artifact directory together. Restore to the same documented paths while the
server is stopped. The backup does not copy raw inference journals; preserve the
experiment output directory separately.

From `ai/`, after committing code and protocol, verify existing artifacts without
downloading or rebuilding, then freeze and execute:

```powershell
$env:HF_HOME = "$PWD/.runtime/huggingface"
$env:HF_HUB_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DVC_NO_ANALYTICS = 'true'
$env:DVC_SITE_CACHE_DIR = "$PWD/.runtime/dvc-site-cache"
$env:DVC_BIN = "$PWD/.runtime/dvc-env/Scripts/dvc.exe"
.venv311/Scripts/python.exe -m roleready_ai.ablation import-exploratory --out outputs/mission003/generation-run-001
.venv311/Scripts/python.exe -m roleready_ai.ablation probe --out outputs/ablation/development-probe-001
.venv311/Scripts/python.exe -m roleready_ai.ablation freeze --seed-evidence outputs/ablation/development-probe-001/probe.json --out evaluation/ablation/freeze.json
# Commit the freeze before generating held-out outputs.
.venv311/Scripts/python.exe -m roleready_ai.ablation run --manifest evaluation/ablation/freeze.json --out outputs/ablation/run-001
# After an intentional stop, resume that same experiment:
.venv311/Scripts/python.exe -m roleready_ai.ablation resume --manifest evaluation/ablation/freeze.json --out outputs/ablation/run-001
.venv311/Scripts/python.exe -m roleready_ai.ablation sync --out outputs/ablation/run-001
```

`--limit N` permits a checkpointed execution segment without changing the frozen
288-set schedule. It is not a smaller evaluation or permission to select cases.
Serving version/digest/settings, frozen code and artifact hashes are checked at
startup and block boundaries. A process lock prevents competing experiment writers.

For a long Windows batch, run the completion monitor in the isolated server
environment (or launch that command as a hidden background process):

```powershell
.runtime/mlflow-env/Scripts/python.exe scripts/complete-ablation.py --experiment outputs/ablation/run-001 --review-out data/private/ablation-review-final-20261122
```

It watches the existing runner, resumes only if its process exits, preserves any
interrupted request, and never replaces a completed case. At 288 recorded sets,
it synchronizes MLflow, exports both final reviewer directories, writes the
pending-human analysis, and saves `outputs/ablation/run-001/completion.json`.
Keep the computer and local Ollama/MLflow services running. A failed supervised
resume requires inspection of `continuation.log`; the monitor does not retry
configuration failures indefinitely. The model/code/settings freeze is unchanged
by this orchestration script or test-only CI fixes.

## Independent human review

```powershell
.venv311/Scripts/python.exe -m roleready_ai.question_review export --experiment outputs/ablation/run-001 --out data/private/ablation-review-001
.venv311/Scripts/python.exe -m roleready_ai.retrieval_review export --out data/private/retrieval-review-001
```

Give each human only their reviewer directory and the rubric. Keep
`PRIVATE_KEY.json` private. Review core questions before opening source-grounding
sheets. Both reviewers rate every successful set independently, using different
randomized orders. Core sheets hide condition, model, citations and timings.
Question text may still reveal the intervention indirectly; perfect blinding is
not guaranteed. Reject changes to immutable exported question/context columns.

Relevance, personalization, technical correctness and difficulty are 1–5 per
question; diversity is 1–5 per set; unsupported assumptions are binary with cited
evidence. Correctness covers generated criteria as well as question premises.
Not-assessable ratings need a rationale and no number. Grounding is a separate
RAG-only second pass. No-RAG has no citation penalty; uncited RAG questions are
reported separately, not silently rated as correctly grounded.

Copy completed files outside the immutable export and retain the names `core.csv`
and `grounding.csv`. Import both passes for both evaluators into NEW files:

```powershell
.venv311/Scripts/python.exe -m roleready_ai.question_review import --bundle data/private/ablation-review-001 --csv data/private/completed-reviewer-1/core.csv --reviewer 1 --out data/private/r1-core-approved.json
.venv311/Scripts/python.exe -m roleready_ai.question_review analyze --bundle data/private/ablation-review-001 --reviews data/private/r1-core-approved.json data/private/r2-core-approved.json --out outputs/ablation/reviewed-analysis-001.json
.venv311/Scripts/python.exe -m roleready_ai.retrieval_review import --csv data/private/retrieval-review-001/reviewer-1.csv --out data/private/retrieval-approved-001.json
```

Use the analogous commands for reviewer 2 and grounding files. Status must be
`human_reviewed`, with reviewer/date; agent/provisional rows never become scores.
Reviewer identity is declared, not authenticated. Preserve both independent
ratings and any later adjudication separately. No human ratings are supplied
by this implementation.

The primary outcome is human job relevance. Average questions within each set,
reviewers, then trials within scenario. The independent sample is scenarios,
not 2,016 questions or 288 sets. Require 30 complete paired scenarios, all arms,
all seeds and both reviewers before confidence intervals. Use 10,000 paired,
role-stratified scenario bootstrap resamples (seed 314159), reporting 95% and
98.33% Bonferroni intervals for three predeclared contrasts. Disclose reviewer
disagreement, not-assessable counts, failures and missing-pair coverage. These
intervals do not establish population-wide or deployment superiority.

Retrieval judgments stay independent: approve complete pooled results before
P@5/P@10, Recall@5/10, MRR@10 and nDCG@10. Recall/nDCG remain pool-relative.
Never infer retrieval quality from generation ratings or vice versa. Investigate
misleading retrieved examples after the frozen evaluation without tuning on it.

## Future technical references

`evaluation/ablation/reference-answer.schema.json` defines a separate, initially
empty reference store. Exact question text hashes bind references to questions;
provenance and explicit human approval are required for future use. No InterviewForge
answers exist. Generated criteria, synthetic benchmark references and question
ratings do not automatically approve a reference or enable scoring.

## Validation and delivery

Run inference-environment `pip check` and AI pytest with offline model settings.
Run `tests/test_mlflow_integration.py` using the isolated server environment and
`PYTHONPATH` pointing to `ai/`. CI adds a real disposable SQLite MLflow server
test; all CI inference uses authored fixtures, never downloads weights. Existing
data/FAISS and frontend/backend checks remain in place. Report the exact delivery
commit/CI URL, freeze hash, MLflow IDs and completed/failed/pending sets. Human
quality results stay null until genuine review, regardless of structural success.

## Verified initial delivery — 22 November 2026

- Harness commit: `06931f65e89105f89476856787d10bec04edb4ee`.
- Pre-inference freeze commit: `0badcbc23a1ee6a4074b760fce2d0d86d648ceb9`.
- Freeze identifier: `fdb56e78d982493d9fff65b74e14efdca654e83167af7affefcf5937dd467801`.
- SQLite dashboard is live at http://127.0.0.1:5000. The controlled parent run is
  `0e43bdc7706e4f09b6ad4434d2dafe30` in experiment 1; retrieval is experiment 2.
- All nine old generation cases and the retrieval benchmark are imported as
  exploratory. Initial blinded question-review sheets and both 607-pair retrieval
  sheets are local under `data/private/`; the full bundle is exported at completion.
- The inference suite passed 179 tests with the optional MLflow test skipped;
  the isolated MLflow suite passed its 16 checks, including an actual server
  restart/artifact-persistence test. The added completion-monitor test passed
  separately. Dependency checks passed in both environments.
- Source snapshots still verify against all pinned hashes and `dvc status --json`
  returns `{}`. No corpus rebuild, model download or reference approval occurred.
- CI exposed a test that accidentally read the local DVC corpus. Commit
  `b249e87b67fef7b25581cfbeb2c1477083f80843` corrects only that fixture; both
  [push](https://github.com/Amin8382/RoleReady/actions/runs/45067035834) and
  [PR](https://github.com/Amin8382/RoleReady/actions/runs/45067040523) CI passed.
- The 288-set batch is running, not claimed complete here. Read `summary.json`
  for current counts and `completion.json` for final synchronization/export evidence.
  Human-approved quality and paired confidence intervals remain null.

Development probes are separate from evaluation: probe 002 recorded two accepted
seeded requests, zero retries, identical observed small JSON responses and 724 ms
combined request latency. This does not establish general GPU determinism. Probe
001 is preserved; its old aggregate counted the second independent request as a
retry. That bookkeeping was corrected before freeze; no held-out output was used.
