# Mission 003: public datasets, local DVC and persistent RAG

Verified on 2026-11-10 in the original `Amin8382/RoleReady` checkout, feature
branch `feat/amin-five-model-runtime`, starting at `a130aba`. This mission adds
an external-source corpus and reproducible retrieval tooling. It does not approve
question quality, scoring references or fine-tuning data.

The existing Python 3.11.18 environment, CUDA runtime, Qwen adapter and small-model
assets are preserved. All 113 package pins in the Mission 001 Windows lock still
match; `torch==2.11.0+cu128`, CUDA 12.8 and `torch.cuda.is_available()==True` were
rechecked on the RTX 4080 Laptop GPU (12,282 MiB reported by nvidia-smi). The
machine's 32 GB RAM and other original specifications are in the
[Mission 001 report](LOCAL_ENVIRONMENT_2026-11-09.md).

No Mission 002.5 implementation/report was present. Mission 002's technical
criteria, semantic-citation and fairness findings remain open. This mission
does not change `generation.py` or `model.py` or repeatedly tune prompts against
the evaluation cases. The accidentally nested `ai/RoleReady/` repository is untouched.

## Source audit and eligibility

Counts below come from the downloaded, hash-verified artifacts, not card claims.
All three Hub repositories expose a `train` split; this descriptive upstream
label does not make an evaluation benchmark eligible for retrieval or training.

| Official publisher/source | Actual raw rows | Retained in RAG | License evidence and decision |
| --- | ---: | ---: | --- |
| [Davichick / InterviewForge_GenDS](https://huggingface.co/datasets/Davichick/InterviewForge_GenDS/tree/25f0a5432554234fcd4cd86c90ab9ed5216a9efa) | 20,444 | 16,466 | MIT declared in pinned README YAML; no separate LICENSE. Eligible for local RAG with publisher attribution and stated limitations. |
| [raghu298 / ml-interview-sft-dataset](https://huggingface.co/datasets/raghu298/ml-interview-sft-dataset/tree/b83f86d352cbfa5b75111157deae8595d7c44e35) | 566 | 0 | Apache-2.0 declared in README, but named upstream HTML/PDF document rights are unverified. Entire source quarantined, including the 73 publisher-claimed handcrafted rows. |
| [Max00035 / ml-systems-interview-bench](https://huggingface.co/datasets/Max00035/ml-systems-interview-bench/tree/891a8edfcfea178790ceab6cee8fa51eda708af8) | 30 | 0 | Full Apache-2.0 LICENSE, README and methodology verified. Reserved for evaluation/reference-rubric research only. |

InterviewForge is **synthetic external data**, not human interview ground truth.
Its publisher reports `mistral:latest` generation without an immutable generator
revision. The card describes answers and 19 roles; the actual CSV has **no answer
column and 38 role labels**. All eight columns are strings: `question`, `keywords`,
`role`, `sector`, `interview_stage`, `interviewer`, `question_category`,
`question_level`. Long contextual scenarios and technical inconsistencies need
review. Published roles/difficulties are not independently calibrated.

ML Interview SFT has `messages` (list), `question`, `answer`, `topic`, `source`
(strings). It contains 531 normalized unique questions and 35 duplicate
occurrences. Of its rows, 493 cite named third-party preparation documents and
73 have the publisher's `curated` source label. Original authorship, document
URLs and redistribution/training rights have not been independently established.
`license_verified=false` records intended-use ineligibility, not denial that the
publisher declares Apache-2.0. Its useful technical content is not a reason to
bypass the quarantine.

ML Systems Bench has 30 unique synthetic questions with IDs, domain, difficulty,
question type and reference answer strings; skill/tag/answer-dimension/expected-
concept/follow-up lists; rubric objects and integer max scores. These illustrative
references and rubrics are not human-calibrated RoleReady scoring references.
Publisher validation code/notebooks were not executed. All sources had zero
malformed rows and zero empty values in their actual columns. Missing *columns*,
such as SFT role/difficulty or InterviewForge answers, remain explicitly unknown.

No observed license introduces a model-use restriction beyond its stated terms,
but publisher declarations do not establish all underlying rights. No source is
approved for SFT by this mission. Pinned source cards/license files remain with
raw snapshots; no large source bodies are committed or uploaded.

### Immutable revisions and hashes

| Source | Exact revision | Data artifact | SHA-256 |
| --- | --- | --- | --- |
| InterviewForge | `25f0a5432554234fcd4cd86c90ab9ed5216a9efa` | `interview_forge_v3_complete.csv` (27,776,542 bytes) | `fed39b9bca11b88eaf4697a15e2e64a0f8bf162ee3d49244904f10671396d3fc` |
| ML Interview SFT | `b83f86d352cbfa5b75111157deae8595d7c44e35` | `ml_interview_sft.jsonl` (1,376,521 bytes) | `f2924fcb96329d07495d2e9c770f049f48f10d0ac50d42ee7016b92c1a3189d7` |
| ML Systems Bench | `891a8edfcfea178790ceab6cee8fa51eda708af8` | `data/questions.jsonl` (53,372 bytes) | `0f63a0697bce6f6efe59c567ed093999efaab2bc0b0933048219c165c2a77d63` |

[The source registry](../data_sources/mission003_sources.json) records every file's
bytes/SHA-256, license evidence, publisher and first verified acquisition time
(2026-11-10 09:31:50–09:31:57 UTC). Eight data/card/license files total 29,246,452
bytes. The downloader requires 40-character revisions, exact sizes/hashes, HTTPS
and bounded files (50 MB maximum each); it refuses to overwrite divergent raw
snapshots and never executes source code. Fixed first-acquisition dates do not
pretend that later replays are new downloads.

## Data architecture and cleaning

Four separate purposes are enforced:

| Purpose | Local/repository location | Policy |
| --- | --- | --- |
| Searchable corpus | `ai/data/mission003/processed/corpus.jsonl` | Versioned knowledge base; **no train/validation/test split required** |
| Retrieval evaluation | `ai/evaluation/mission003/retrieval_queries.jsonl`; DVC ranking/review pools | Independent queries and separate relevance judgments; documents under judgment remain searchable |
| Generation evaluation | `ai/examples/mission003/generation_scenarios.json` | Three fresh synthetic CV/job cases; never indexed or used as SFT |
| Future supervised data | `ai/data/fine_tuning/README.md` | No training data/run; future reviewed data needs its own grouped train/validation/test policy |

The canonical `corpus-1.0` record has `record_id`, `question`, primary `role`,
`roles`, nullable `topic`, `competencies`, nullable `difficulty`, nullable
`question_type`, `source_id`, `source_revision`, occurrence-level `provenance`,
`schema_version`, `purpose=retrieval_corpus`, `reviewed=false` and
`reference_answer=null`. Provenance includes repository/URL, exact source file,
row, SHA-256, original labels, upstream split, authorship and license decision.
The legacy SFT loader explicitly rejects corpus-purpose records. Old TRAIN-bank
interfaces and tests remain supported; the internal `split="corpus"` property is
only a compatibility marker and is not serialized as an SFT partition.

Processing normalizes NFKC Unicode and whitespace, preserving fenced-code
indentation. Normalized question hashes produce stable `rrq-` IDs. Deduplication
case-folds ordinary prose and removes trailing sentence punctuation while
preserving internal operators and `C++`/`C` distinctions. Exact duplicates merge
occurrence provenance and roles rather than losing sources. Malformed rows,
unknown/out-of-scope roles and reserved benchmark overlaps have explicit rejection
reasons. Answers go to a separate unreviewed store, never automatically into
prompts or scoring. Evaluation/quarantined sources are excluded regardless of
upstream split. The 30 benchmark questions plus follow-ups reserve 90 normalized
keys; exact overlap with the retained corpus was zero. Semantic leakage beyond
these exact keys is not proven absent.

`roles-1.0` maps explicit aliases and preserves specialties. `AI/ML Engineer`
becomes both Machine Learning Engineer and AI Engineer (576 applicable records
each, not disjoint). Software Engineer search expands to explicit software
specialties; **no source row is falsely relabeled Software Engineer**. All eight
priority roles have direct or documented family search coverage. There are 29
primary canonical roles, 30 applicable labels and 16 source topics. Unknown roles
are not converted to general questions. Behavioral material remains searchable.

Actual cleaning: 21,040 input rows; 566 quarantined; 30 evaluation-only; 3,978
InterviewForge rows out of scope; **16,466 final records**, zero invalid retained-
source rows, zero exact duplicate removals and zero reserved exact overlaps.
Excluded role families are Network Engineer, Engineering Manager, Scrum
Master/Agile Coach, Sales/Solutions Engineer, Technical Product Manager, UX/UI
Designer, SOC Analyst and Penetration Tester. Broad software/data/AI specialties
were retained rather than limiting the corpus to eight job titles. Difficulty
counts are easy 5,470 / medium 5,500 / hard 5,496. Two unmapped category types
remain null (2,053 records); source topic/keywords are preserved. No reference
answers exist in the eligible CSV, so `references.unreviewed.jsonl` is empty.

The [source audit](../evaluation/mission003/source_audit.json) records full counts,
column types, missing values, role/topic coverage, rejection statistics and
transformation code hashes. Corpus bytes: 30,749,193; SHA-256
`f4e66cff619dca77d763b9529bcf46df985bf60a02d8ee5c4b65638af34d6cc9`.

## DVC and actual disk locations

All paths are relative to
`C:\Users\gasmi\Downloads\amin\RoleReady`:

- `ai/data/mission003/raw/<source_id>/<revision>/<publisher-file>`: immutable
  public snapshots, including quarantined/evaluation-only audit files.
- `ai/data/mission003/processed/`: corpus, rejection log, empty reference store,
  manifest. `ai/data/mission003/index/`: FAISS, complete metadata and semantic flags.
- `ai/data/mission003/retrieval_runs/run-001/` and `run-002/`: actual rankings,
  unjudged relevance JSON and human-review CSV pools.
- `ai/outputs/mission003/generation-run-001/`: private-by-default full prompts,
  attempts, generated results and GPU samples; never committed or DVC-tracked.
- `ai/.runtime/huggingface/`: existing model cache; `.dvc/cache/`: local DVC cache.

Git tracks `.dvc/.gitignore`, empty `.dvc/config`, `.dvcignore`, `dvc.yaml`,
`dvc.lock`, `raw.dvc`, `retrieval_runs.dvc`, source registry/parameters and code.
DVC tracks the 8 raw files, processed directory, persistent index directory and
public-source retrieval pools. `.gitattributes` fixes pipeline source/config
line endings; no unrelated checkout is renormalized in Git.

`prepare_corpus` verifies raw snapshots and emits deterministic artifacts;
`build_index` depends on corpus, source code and explicit device/duplicate
threshold parameters. The selected Python is controlled by a temporary PATH,
not a permanent machine setting. DVC 3.67.1 is isolated from the verified model
environment. `dvc repro` passed; a real-data `dvc repro --force prepare_corpus`
produced **byte-identical hashes for all four processed files**, kept the index
unchanged, and `dvc status --json` returned `{}`. See
[the replay proof](../evaluation/mission003/dvc_reproducibility.json).

**No remote, cloud credentials, data push or external upload is configured.**
A new checkout cannot `dvc pull` these local artifacts. It must reacquire the
pinned public sources, provision the pinned model/runtime and run the stages,
or obtain an explicitly approved shared-data solution later. Local deterministic
replay does not promise byte-identical floating-point embeddings on every
hardware/library combination.

## Persistent BGE/FAISS measurements

Existing cached `BAAI/bge-small-en-v1.5`, revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, weights SHA-256
`3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad`, is
loaded locally without downloading. Embedding text is question + normalized
roles + source topic + source keywords/competencies + difficulty, explicitly
versioned `corpus-metadata-v1`. Query text retains the existing query/role format.
All 16,466 embeddings are float32, 384-dimensional and L2-normalized. Exact
CPU `IndexFlatIP` searches normalized inner product (cosine); CUDA performs the
embedding computation. No approximate index or new model is introduced.

The 25,291,821-byte FAISS file (24.12 MiB) has SHA-256
`ecc809be80eff1fd088997443d080003bf5ee0eff577e0d73c72c2593f8121f0`.
Full metadata is 37,799,072 bytes, including all source provenance, vector-order
checksum, document fingerprint, corpus/model/taxonomy revisions and index hash.
Reload reads stored vectors **without re-encoding** and checks counts, dimensions,
metric, checksums and expected revisions. Full record mapping equality and three
before/after self-query probes passed; probes establish persistence, not quality.

Final local rebuild observations:

| Operation | Measured time |
| --- | ---: |
| Optional library imports / encoder initialization | 26.409 s / 1.456 s |
| All embeddings, batch size 64, CUDA | 128.442 s |
| FAISS add/build | 18.132 ms |
| Save / reload without encoding | 8.152 s / 5.296 s |
| Semantic candidate search | 1.425 s |

Peak PyTorch CUDA allocation was 480,751,104 bytes (458.48 MiB); sampled peak
process RSS was 1,687,183,360 bytes (1.57 GiB). RSS includes Python/model/corpus
overhead; CUDA allocation excludes other processes/non-PyTorch memory. Earlier
DVC build embeddings took 41.770 s, showing material local timing variation;
these are observations, not controlled throughput guarantees. Max tokenized
embedding length was 284 of 512; zero texts were truncated. Top-six-neighbor
cosine screening at 0.94 flagged 89 possible semantic duplicate pairs; **zero
were automatically removed**. Review is pending, screening is not exhaustive.
[Full final index evidence](../evaluation/mission003/index_benchmark.json).

## Retrieval evaluation and error analysis

There are 32 independent agent-authored search queries: four across each of the
eight priority roles, authored before inspecting rankings. Both systems return
ten valid text/ID hits for 32/32 queries. Their union contains 607 query/document
pairs. This measures response coverage, not relevant-result coverage. The index
contains 16 topics and the manifest reports actual role/topic counts; query
competencies are a small selected sample, not a representative population study.

On CPU query encoding/search, 3 observations per query/method (96 per method):

| Method | Median | p95 |
| --- | ---: | ---: |
| Lexical | 45.606 ms | 154.611 ms |
| BGE/FAISS | 49.045 ms | 171.522 ms |

Timing includes encoding/scoring/role filtering, excludes loading, and may include
warm-up/noisy system activity. A bounded cache of pure role-compatibility results
removed a measured normalization bottleneck. **All 64 ranked ID lists remained
identical** against the prior run. These timings do not establish relevance
superiority for either method. See [timing observations](../evaluation/mission003/retrieval_benchmark.json).

Sixteen selected judgments across eight queries are explicitly
`agent_provisional`, with no human approvals. **Human-reviewed pairs: 0.**
Official P@5, Recall@5, Recall@10, MRR@10 and nDCG@10 remain null. The tooling
requires corpus/query hash agreement, valid IDs, explicit reviewer/date, a fully
approved pooled result set and at least one assessed positive. Recall/nDCG are
pool-relative even after review; MRR is explicitly truncated at rank 10.
Formulas, review/import commands and limitations are in
[the evaluation guide](../evaluation/mission003/README.md). No metric is computed
from provisional labels and presented as human ground truth.

Observed provisional failure examples:

- RAG-context search retrieved conversational-model release prioritization
  (`rrq-d84454140552ac819c6f3035`), not retrieval grounding. Related subject words
  do not establish competency relevance.
- Prediction-time feature/leakage search returned explainability/regulatory
  discussion (`rrq-e5a488a629ba1d88a3fd1436`), a different evaluation need.
- Exclusive booking search returned server overload
  (`rrq-c8b2f349604b814a374ccfd8`), not transaction/uniqueness logic.
- Kafka duplicate-event/recovery search found a directly related scenario
  (`rrq-7a06eb319a1b96af2ae4b12f`); this agent observation needs independent review.

The corpus is rich in long scenario/behavioral questions but thin in narrowly
targeted fundamentals, RAG and leakage material. Some original scenarios mix
irrelevant regulatory constraints or confuse framework tradeoffs. Source rights,
technical screening and human relevance labeling should improve before corpus
expansion or retriever claims.

## Real Qwen comparison: nine cases, 63 questions

The fixed batch ran the existing local `roleready-qwen35-4b:8k`, parent
`qwen3.5:4b-q4_K_M`, GGUF Q4_K_M, 4.2B reported parameters, llama.cpp runner,
Ollama 0.40.15. Digest:
`27af9727272c8f96be4302b0283fa045132389692e9c86949081d18484d1cfb8`.
Endpoint: `http://127.0.0.1:11434/v1/chat/completions`. Serving context 8,192,
max output 4,096, temperature 0.2, top_k 20, top_p 0.95, presence penalty 1.5;
strict response JSON schema, non-thinking `reasoning_effort=none`, timeout 600 s,
at most 2 attempts. No new Qwen/Prometheus download or permanent service changes.
The existing alias's family/quantization and unchanged digest were verified.

Each scenario is fresh synthetic English evaluation input. BGE query encoding
uses CPU while Qwen uses the GPU. RAG selects five actual corpus examples to fit
the existing context. **Every attempted prompt was checked for the exact full
retrieved question texts and IDs**, not vectors alone. Saved final outputs were
revalidated against allowed IDs and literal input evidence.

| Synthetic case | Mode | Valid questions | Attempts | Total generation incl. retry | Peak device memory |
| --- | --- | ---: | ---: | ---: | ---: |
| Junior Data Analyst / city-bike project | None | 7 | 2 | 185.290 s | 6,123 MiB |
| Same | Lexical | 7 | 1 | 98.855 s | 6,054 MiB |
| Same | BGE | 7 | 1 | 114.831 s | 6,076 MiB |
| Junior MLE / support-ticket classifier | None | 7 | 1 | 121.070 s | 7,245 MiB |
| Same | Lexical | 7 | 1 | 134.606 s | 7,129 MiB |
| Same | BGE | 7 | 1 | 118.260 s | 6,581 MiB |
| Junior Backend / parcel API | None | 7 | 1 | 112.930 s | 6,402 MiB |
| Same | Lexical | 7 | 1 | 139.457 s | 6,500 MiB |
| Same | BGE | 7 | 1 | 161.540 s | 6,617 MiB |

Nine final structural passes / nine cases, 63 questions; 9/10 raw attempts passed
validation. The first no-RAG analyst attempt was rejected for treating missing
CV evidence as missing ability; its raw attempt and rejection are preserved
locally, and the existing bounded retry passed. Total generation time summed
across cases is 1,186.839 s. First request 96.712 s, retried request 88.527 s;
later request latencies are recorded separately. The API omits native model-load
duration, so these are **not claimed as controlled warm-only timings**. Per-case
nvidia-smi GPU utilization reached 100%; memory measurements are total-device
samples, not isolated Qwen allocations. No process-specific VRAM inference is
invented. [Measured summary and all case review findings](../evaluation/mission003/generation_evidence.agent.json).

Agent inspection covered all 63 questions and their criteria/citations. No
obvious assertion of a past undocumented candidate incident or first-person
candidate question was observed; the presented incidents are hypothetical.
Literal evidence and source membership passed. No obvious semantic duplicate
pair was found, but analyst communication/uncertainty questions overlap and
diversity is not independently rated. Mostly easy/medium labels are not human
calibrated; an easy fleet-scaling question is inappropriate for the junior scope.

**Qualitative gate remains open**, with concrete findings:

- Analyst BGE Q6/Q7 import fleet scaling/delivery modeling rather than junior
  city-bike analytics. Lexical Q5 imports a six-month ML roadmap. Several SQL/
  dashboard questions cite sources that actually discuss roadmaps or negotiation.
- MLE BGE Q1 says validation should use only training data; Q2 suggests
  stratification without respecting the documented chronological split. Both
  need technical review. Some citations support only broad ML architecture.
- Backend BGE Q1 incorrectly suggests request IDs establish resource ownership;
  they are correlation identifiers, not authorization. Q7 imports ERP inventory
  integration absent from the job. Lexical Q2's criteria conflict about adding
  indexes while forbidding schema alteration. Several questions cite the wrong
  retrieved scenario, despite all source IDs being valid.
- Some criteria unfairly constrain hypothetical designs to documented experience
  or repeat missing-production qualifiers. These are not approved scoring rules.

Representative unedited BGE questions, retained with explicit unreviewed status:

- Analyst: “How would you ensure data quality when validating trip and station
  data using SQL joins and aggregations?” → `rrq-3e0f7185c2f800f877b4a1cb`.
  The ID is valid but the cited source is route-change negotiation: weak grounding.
- MLE: “How would you document your experiment parameters to ensure
  reproducibility of your support-ticket classifier?” →
  `rrq-681efc24bd8cb23a765248d0`. The source is resource prioritization, not
  experiment tracking: a useful question with weak citation alignment.
- Backend: “What would you do if a colleague discovers a potential blocking
  issue in the backend code during late-stage testing?” →
  `rrq-ac7c02b05fbdeffb3cc9c747`. This hypothetical aligns with the source.

Three [small generated samples](../examples/mission003/) preserve all 21 BGE
questions/criteria/IDs, including failures of qualitative expectations. All
references remain **unreviewed, unsuitable for scoring**. This demonstrates
working data/index/Qwen integration, not human-validated quality or a RAG win.

## Reproduce in Windows PowerShell

Run from the original repository root. Use the existing runtime from Mission 001;
do not recreate it or install data-tool dependencies into it. DVC was installed
with these commands (the venv creation is a first-install step only):

```powershell
ai/.venv311/Scripts/python.exe -m venv ai/.runtime/dvc-env
ai/.runtime/dvc-env/Scripts/python.exe -m pip install -r ai/requirements-data-tools.txt
ai/.runtime/dvc-env/Scripts/python.exe -m pip check
$env:DVC_NO_ANALYTICS = 'true'
$env:HF_HOME = "$PWD/ai/.runtime/huggingface"
$env:HF_HUB_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:PATH = "$PWD/ai/.venv311/Scripts;$env:PATH"
```

Acquire/verify the small pinned public snapshots (HF offline setting affects
model loading, not this explicit public dataset downloader):

```powershell
Set-Location ai
.venv311/Scripts/python.exe -m roleready_ai.acquisition --registry data_sources/mission003_sources.json --raw data/mission003/raw
.venv311/Scripts/python.exe -m roleready_ai.acquisition --registry data_sources/mission003_sources.json --raw data/mission003/raw --verify-only
Set-Location ..
ai/.runtime/dvc-env/Scripts/dvc.exe repro
ai/.runtime/dvc-env/Scripts/dvc.exe status --json
ai/.runtime/dvc-env/Scripts/dvc.exe remote list
```

The cached pinned BGE weights must already exist. A missing cache/hash mismatch
fails explicitly, without downloading; follow Mission 001 provisioning separately.
For a fresh approved snapshot, `dvc add ai/data/mission003/raw` updates the local
pointer; after intentional pipeline changes, inspect/commit `dvc.lock`. Avoid
overwriting previous evaluation output directories or human annotations.

Independent index build, retrieval benchmark and provisional-label gate:

```powershell
Set-Location ai
.venv311/Scripts/python.exe -m roleready_ai.indexing --corpus data/mission003/processed/corpus.jsonl --out data/mission003/index --device cuda --duplicate-threshold 0.94 --report outputs/mission003/index-benchmark.json
.venv311/Scripts/python.exe -m roleready_ai.retrieval_evaluation benchmark --corpus data/mission003/processed/corpus.jsonl --index data/mission003/index --queries evaluation/mission003/retrieval_queries.jsonl --out data/mission003/retrieval_runs/run-003 --report outputs/mission003/retrieval-benchmark-new.json --device cpu --repeats 3
.venv311/Scripts/python.exe -m roleready_ai.retrieval_evaluation metrics --rankings data/mission003/retrieval_runs/run-002/rankings.json --judgments evaluation/mission003/provisional_judgments.json
```

The last command reports `human_review_required` and null official metrics.
For human CSV review/import, use the evaluation guide; do not turn AI labels into
human labels automatically. No DVC remote/push command is required or authorized.

To repeat the declared Qwen demonstration only when intentionally conducting a
new experiment, ensure Ollama already runs with the existing approved alias:

```powershell
.venv311/Scripts/python.exe -m roleready_ai.corpus_demo --corpus data/mission003/processed/corpus.jsonl --index data/mission003/index --out outputs/mission003/generation-run-002
```

The command is loopback-only, rejects other loaded Ollama models, never pulls
weights and refuses an existing output directory. For application integration,
`roleready_ai.run` supports `--bank-format corpus --bank .../corpus.jsonl
--retrieval bge-faiss --index data/mission003/index`; the old default legacy bank
and lexical behavior remain available. Raw prompts/evaluation outputs stay local.

## Validation, delivery and next work

The final runtime suite passed **164 tests** including all 98 pre-mission tests,
real FAISS persistence without model downloads, data/schema/provenance/leakage,
hand-checked metric fixtures, review-gating/import and an actual disposable DVC
reproduction/corruption-rejection test. The dependency-light environment passed
155 tests with one optional FAISS module skipped. Its DVC test used the isolated
tool via `DVC_BIN`. Both environments and the separate DVC environment passed
`pip check`; `compileall` passed. No model download occurs in unit tests.

```powershell
$env:DVC_BIN = "$PWD/.runtime/dvc-env/Scripts/dvc.exe" # from ai/
.venv311/Scripts/python.exe -m pytest -q
.venv311/Scripts/python.exe -m pip check
.venv311/Scripts/python.exe -m compileall -q roleready_ai
```

A Windows temporary DVC test initially hit path-length limits. The disposable
test now uses a short cache path instead of changing machine/security settings.
An initial optional `psutil` dependency was replaced by a standard-library
Windows/Linux RSS reader; the verified model environment gained no packages.
PyTorch emits its known Windows elastic-output-redirection warning during real
loads; successful process exit/results are checked separately.

CI retains the original AI/backend/frontend jobs and adds an isolated corpus/DVC/
FAISS job (`.[test,index-test]`, DVC 3.67.1) with real FAISS and no Torch/weights.
GitHub run results for the delivered commit are reported in the final delivery;
this document does not use an older green run as evidence for new changes.
Only named source/config/test/docs/DVC-pointer/small-synthetic-example files are
staged. Data bodies, weights, caches, audio, private CVs and full raw prompts stay
out of Git. No main merge or force-push is part of this mission.

**Recommended Mission 004:** independent human review of the pooled retrieval
results and technical criteria; approve a licensed fundamentals/RAG supplement;
then compare retrieval configurations on new held-out scenarios. Correct the
documented authorization, temporal-evaluation and citation-quality problems
using separate development cases before scoring/backend integration. Select an
approved DVC sharing strategy separately. Fine-tuning and Prometheus remain
deferred; more structural passes cannot resolve these quality/rights gates.
