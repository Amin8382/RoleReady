# Mission 002: local Qwen and synthetic RAG evidence

Base: Mission 001 commit `d7aecce`, branch `feat/amin-five-model-runtime`.
The existing Python 3.11.18 CUDA environment and small-model adapters are preserved.
No new Python dependencies, system software, security settings or fine-tuning are
required. Prometheus is outside this mission.

## Artifact and local serving

The user explicitly approved the approximately 3.3 GB download of
[`qwen3.5:4b-q4_K_M`](https://ollama.com/library/qwen3.5:4b-q4_K_M).
Ollama CLI and the existing loopback service both reported **0.40.15**. The
preflight GPU reading was 12,282 MiB total / 10,288 MiB free, with no Ollama
models loaded. The source listing identifies Qwen3.5, Q4_K_M, 4.21B language
parameters and a separate BF16 vision projector; this task uses text only.

The approved pull uses Ollama's existing user model cache outside the repository;
it does not change the Mission 001 Hugging Face cache or Python environment.

```powershell
# From repository root, after explicit download approval:
ollama pull qwen3.5:4b-q4_K_M
cd ai
ollama create roleready-qwen35-4b:8k -f examples/mission002/Modelfile
$env:ROLEREADY_QWEN_BASE_URL="http://127.0.0.1:11434/v1"
$env:ROLEREADY_QWEN_MODEL="roleready-qwen35-4b:8k"
$env:ROLEREADY_QWEN_REASONING_EFFORT="none"
$env:HF_HOME="$PWD/.runtime/huggingface"
$env:HF_HUB_DISABLE_TELEMETRY="1"
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN="1"
$env:HF_HUB_DISABLE_XET="1"
.venv311/Scripts/python.exe -m roleready_ai.qwen_demo --model roleready-qwen35-4b:8k
```

The local alias reuses the approved weights and sets context to **8192**, output
limit to **4096**, and temperature to **0.2**. This follows Ollama's documented
[context configuration for OpenAI-compatible clients](https://docs.ollama.com/api/openai-compatibility#setting-the-local-context-size),
which cannot set context size through the standard chat request. Calls remain
sequential, with only one large model loaded. No permanent environment-variable
or service configuration changes are needed; the existing local service is reused.

## JSON and evidence boundaries

`model.py` remains the existing OpenAI-compatible adapter. It now supports explicit
JSON object/schema enforcement and optional `reasoning_effort`, records safe
response metadata, checks returned model identity and `finish_reason=stop`, and
rejects oversized, malformed, fenced, non-object or nonstandard JSON and duplicate
JSON keys. It does not strip thinking text or repair malformed responses.

The tested serving profile requests `reasoning_effort="none"`. Ollama documents
[non-thinking controls](https://docs.ollama.com/capabilities/thinking) and
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
The installed version's [OpenAI conversion code](https://github.com/ollama/ollama/blob/v0.40.15/openai/openai.go)
also maps JSON schemas to its native grammar and reasoning controls to thinking
settings. Actual responses verified the selected model, `finish_reason=stop`,
strict JSON and zero returned reasoning characters. The default adapter timeout
is now 300 seconds (bounded to 600): the measured cold call exceeded the old
120-second default. The demo's warm structured requests used 240 seconds.

`generation.py` retains seven-question validation and source-ID checking, adds
strict field/type checks, repeated-value and near-identical wording checks,
guards against some explicit missing-ability claims, and allows at most two
attempts by default (hard maximum three). Invalid attempts remain visible in
the result. Transport/server failures are explicit errors, not a silent fallback
to unconstrained generation. Semantic factuality is not proven by a JSON grammar.

The prompt receives **actual retrieved question text, IDs, roles and retrieval
scores**, never just vectors. CV, job and retrieval strings are untrusted evidence.
Every reason must include one literal 8-160 character CV excerpt and one literal
job excerpt, labeled `CV: [...]; Job: [...]`. Both are checked against the actual
inputs. Invented, missing or repeated anchors reject the attempt. Literal anchors
provide traceability; they do not prove every surrounding claim is entailed.
Before decoding, the per-input schema restricts evidence to at most 24 literal
clauses from each input and restricts citation strings to retrieved IDs. This
requests literal choices; post-response validation rejects invented/combined quotes without rewriting responses.
The rationale ends with a fixed neutral uncertainty statement, rather than a
free-form conclusion about candidate ability. First-person prefixes, some
unsupported-incident phrases, deficit labels and selected undocumented past-action claims are rejected.
These are conservative heuristics, not a complete semantic-factuality validator.
CLI outputs explicitly carry `quality_status=unreviewed_model_output`.
Requirements not evidenced by the CV must lead to hypothetical questions rather
than invented prior experience or missing-ability judgments.

Final review tightened the generation policy: every text starts `How would you`
or `What would you`, and every criterion starts `The answer should`. Criteria
must describe proposed answer content and reject selected personal-history and
missing-experience phrases. Entry/junior practice is deliberately limited to
bounded easy/medium questions in both the input-derived schema and validation;
mid/senior retains hard questions. These are conservative practice policies,
not empirical difficulty calibration. The consolidated prompt asks for distinct
competencies and project-specific wording; adherence still requires inspection.

Question text is bounded to 350 characters, skill to 80, and each criterion to
200 (at most three). A question may cite one primary retrieved source or none;
extra secondary IDs are rejected rather than truncated. This avoids citation
padding observed during inspection. The six-field output shape is unchanged.

Schema enforcement is **requested**, not assumed infallible. The installed
server returned some malformed/truncated content despite HTTP 200 and a schema
request; `finish_reason=length` responses were rejected, and bounded retries
sometimes recovered. Only fully parsed and validated final responses count as
structural passes. Raw rejected content is retained locally; it is never repaired
or silently accepted. The demo now exposes a bounded `--timeout` (default 300,
maximum 600 seconds); the final run explicitly uses 600 after a 240-second call
timed out during battery operation. The application adapter default stays 300.

## Reproducible synthetic demonstration

`examples/mission002/` contains three synthetic CV/job scenarios and 18 original,
TRAIN-only question records: five per role and three general questions. There is
no scraped dataset, real CV or held-out quality claim. References remain unreviewed
and are not used for scoring or SFT.

`qwen_demo.py` refuses remote endpoints and missing models, never pulls weights,
and uses the existing cached BGE revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` in local-files-only mode. BGE runs on CPU
to keep its allocations separate from Qwen's GPU measurements. FAISS uses the
existing normalized inner-product implementation. Each scenario runs with lexical
retrieval and with BGE/FAISS, for six real generation attempts/runs.

Raw synthetic prompts, responses, rejected attempts, per-run JSON and sampled GPU
measurements are kept under ignored `ai/outputs/qwen-mission002/`. A reviewable
synthetic sample can be published separately after validation; raw/private outputs
and model artifacts must not be staged.

The BGE cosine screen flags question pairs at 0.86 or above for review. It is a
heuristic, not calibrated semantic-duplicate detection. All results still require
explicit inspection of relevance, documented CV grounding, citation relevance,
competency diversity and missing-evidence wording. This demonstration is not a
two-reviewer, held-out quality evaluation.

## Delivery status

**Runtime and structural validation pass. The qualitative gate remains OPEN.**
This report does not declare full Mission 002 quality completion. The exact 42
raw questions are published with per-question agent findings, including unresolved
technical criteria and citation weaknesses. No generated criterion is approved for scoring.

## Actual artifact, endpoint and measurements

| Item | Verified value |
| --- | --- |
| Source | `qwen3.5:4b-q4_K_M`, GGUF Q4_K_M, reported 4.2B; 3,324,173,934 bytes |
| Source manifest SHA-256 | `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` |
| Served profile | `roleready-qwen35-4b:8k` |
| Profile manifest SHA-256 | `27af9727272c8f96be4302b0283fa045132389692e9c86949081d18484d1cfb8` |
| Server | Ollama 0.40.15 / llamacpp, Windows |
| Tested endpoint | `http://127.0.0.1:11434/v1/chat/completions` |
| Requests | Context 8192; max output 4096; temperature 0.2; stream false; JSON schema; reasoning_effort none |
| Timeout | Demo explicitly 600 seconds; application adapter default 300 seconds |
| GPU | RTX 4080 Laptop, 12,282 MiB; `ollama ps` reported 100% GPU |
| Model allocation | `/api/ps`: 3,364,911,840 bytes, about 3209 MiB |
| Final sampled whole-device peaks | 5566-5621 MiB used; per-case utilization peaks 73-100% |
| Power | Final run verified on AC; observed P0 / 2445 MHz. Earlier battery observations included P8 / 210 MHz. No power settings changed. |

The approved language/projector layers are reused by the local profile; its
different manifest represents serving parameters, not new weights. This is text-only
inference, not validation of the vision projector. BGE uses the pinned Mission 001
revision on CPU; FAISS remains CPU. No other large model was loaded.

## Final six-case structural results

Recorded directory: `ai/outputs/qwen-mission002/attempt-15/`.

| Synthetic scenario | Retrieval | Total wall s | Accepted response s | Requests | Valid questions |
| --- | --- | ---: | ---: | ---: | ---: |
| Junior Data Analyst | lexical | 69.930 | 17.900 | 2 | 7 |
| ML Engineer | lexical | 15.766 | 15.748 | 1 | 7 |
| Backend Developer | lexical | 17.685 | 17.648 | 1 | 7 |
| Junior Data Analyst | bge-faiss | 68.288 | 16.997 | 2 | 7 |
| ML Engineer | bge-faiss | 17.338 | 17.204 | 1 | 7 |
| Backend Developer | bge-faiss | 17.322 | 17.189 | 1 | 7 |

Final-case acceptance is **6/6**, producing **42/42 structurally valid questions**
and **84 unchanged literal evidence excerpts**. Four cases succeeded on their
first request; the two Data Analyst cases each rejected one 4096-token,
`finish_reason=length` response and recovered on their bounded second attempt.
Thus **6/8 model requests were accepted**, not eight flawless generations.
All accepted responses returned the requested model, `finish_reason=stop` and
zero reasoning characters. No rejected output was repaired or promoted.

Total monitored case latency is **206.329 s**,
including retrieval, validation and rejected attempts. It excludes Python imports,
BGE loading and subsequent similarity screens. Accepted warm chat-response wall
times were **15.748-17.900 s**.
The OpenAI endpoint supplied no separate load/prefill/decode timings for these
requests; client wall time must not be described as pure decoding time.

A separate warm native short call took **1.144 s**, with **12.844 ms loading**,
**332.139 ms prompt evaluation** and **450.330 ms decoding** for 31 tokens.
The original cold short call took **201.201 s**, including **103.352 s loading**,
**92.261 s prompt evaluation** and **5.556 s decoding** for 33 tokens. Cold baseline
and sampled whole-GPU peak were 1680 / 5736 MiB. Cold initialization, battery-limited
runs and steady AC generation must be kept separate.

Both retrievers select the same eight role-compatible TRAIN records here, in
different orders. This proves both integration paths, not retrieval superiority.
Whole-GPU samples include desktop/other processes and are sampled, not exact peaks.

## All-42 inspection and remaining quality blockers

The [unedited samples](../evaluation/mission002/synthetic_samples.json) include
retrieved question texts and IDs. The [runtime evidence](../evaluation/mission002/runtime_summary.json)
records exact hashes, parameters, token counts, timings, GPU measurements, retries
and run history. The [agent review](../evaluation/mission002/validation_review.json)
contains one note for every question and separates these observations from automated gates.

Agent inspection found no fabricated CV experience, no past incident attributed
to a candidate without CV evidence, and no first-person candidate question text.
All citation IDs belong to actual retrieved records. New workloads, conflicts and
failures are interview hypotheticals. Criteria are prospective; generic context
such as previously cleaned rows is allowed when documented. No obvious duplicate
questions were found, though Data Analyst/BGE q2/q3 share missingness context and
need diversity review. Maximum pair cosines span
0.73915-0.85628, below the heuristic 0.86 screen;
this is not proof of semantic distinctness. Easy/medium labels and broad competency
coverage appear suitable for junior practice, without empirical calibration.

**The following findings prevent qualitative/scoring sign-off:**

- Data Analyst/BGE q1 says aggregated sales sums should match source row counts,
  generally a units error. This raw criterion is not approved for scoring.
- Backend/BGE q1 suggests `UNIQUE(user, time_slot)`, which permits different users
  to occupy the same exclusive slot. The constrained resource must be established.
- Backend lexical q2/q4 cite query-performance/observability records with weak
  topic alignment. Membership validation does not establish semantic grounding.
- Backend/BGE q6/q7 include meta-rules against claiming scaling/Kubernetes
  experience. Missing documentation must not penalize genuine unlisted experience.
- Other criteria remain prescriptive or imprecise, including seasonality versus
  artifacts, reproducibility guarantees and leakage/monitoring diagnostics.
- Some rationale anchors and texts remain generic or weakly connected. The prompt
  target of three explicit project details is not consistently achieved.

Earlier ML inversion/target-handling/drift mistakes now have targeted regressions
and clearer instructions. These narrow checks do not establish general technical
correctness. The remaining examples demonstrate why a semantic/reference review
gate is necessary. No independent human review or question-quality pass rate is claimed.

Representative actual questions:

- ML/BGE, `syn-ml-reproduce`: "How would you ensure your fraud classification
  pipeline remains reproducible if a new Python library version introduces subtle
  behavior changes?"
- Data Analyst/BGE, `syn-da-dashboard`: "How would you maintain Power BI reports
  while ensuring they remain accurate when source data changes?"
- Backend/BGE, `syn-be-security`: "How would you verify that the JWT authentication
  middleware correctly restricts access to the booking endpoint?"

## Preserved failures and iterations

| Recorded run | Outcome and response |
| --- | --- |
| attempt-01 | Short real inference passed; BGE setup stopped because an offline full-repository snapshot expected unneeded ONNX/bin files. Fixed by requesting only the Mission 001 cached subset. |
| attempt-02 | 0/6 accepted after two attempts each: free-form reasons ignored the literal-evidence format. All raw responses retained. |
| attempt-03 | 2/6 accepted: format was enforced, but copied evidence still added words or combined noncontiguous clauses. |
| attempt-04 | 6/6 structurally valid; agent inspection rejected first-person questions and unsupported deficit claims in free-form reasons. |
| attempt-05 | 6/6 structurally valid; inspection found an implied undocumented slow-query incident and past-action assumptions in criteria. |
| attempt-06 | 6/6 structurally valid; inspection found a remaining "lack of production monitoring experience" assertion. Added a regression/guard. |
| attempt-07 | 6/6 under the earlier structural policy; final review rejected assumed lack of professional experience and an undocumented monitoring-history criterion. Preserved in local artifacts and commit `e51bef5`. |
| attempt-08 | 6/6 structurally valid; review still found routine junior tasks labeled hard. Added explicit entry/junior difficulty policy. |
| attempt-09 | 6/6 structurally valid; review found a past SQL-join presupposition and a criterion assuming no prior experience. Tightened hypothetical wording and criteria checks. |
| attempt-10 | 5/6: Data Analyst/BGE hit its 240-second timeout on battery; complete prompt/error metadata retained. Inspection also found loose secondary citations and an incorrect target-independence criterion. |
| attempt-11 | 6/6 after bounded retries; two initial responses reached 4096 tokens and were rejected. Measurements span battery and AC transition. A concrete SQLite prompt example contaminated an ML question; removed it from shared instructions. |
| attempt-12 | 5/6 on AC: Data Analyst/BGE was rejected twice, including a false positive on a prospective "back to you" criterion. Narrowed the guard while preserving past-work checks, and added a guard for undocumented current-implementation details. |
| attempt-13 | 5/6: the Data Analyst/BGE response referred to previously cleaned 5000 rows and a previously queried SQLite database, both documented. Removed the blanket "previously" ban; prospective criteria may use documented context while unsupported deployment/test claims remain rejected. |

| attempt-14 | 6/6 structural; inspection found ML availability/feature-handling/drift misconceptions. Preserved the full 42-question review and added targeted regressions/instructions. |
| attempt-15 | 6/6 final structural passes; 42 outputs inspected. Remaining technical, fairness and citation findings are explicitly open, not silently accepted as scoring references. |


All raw prompts, responses, rejected attempts and per-case files remain local
under ignored `ai/outputs/qwen-mission002/attempt-01` through `attempt-15`.
Specific earlier failure examples are preserved in the review artifact. The prior
published attempt-07 samples remain in commit `e51bef5`. Iterating on these same
three synthetic cases is prompt development, not a held-out benchmark or accuracy estimate.

## Validation and reproducibility

From `ai/`, after configuring the existing model profile as above, use a NEW output
directory for every run:

```powershell
.venv311/Scripts/python.exe -m roleready_ai.qwen_demo --model roleready-qwen35-4b:8k --timeout 600 --out outputs/qwen-mission002/repeat-001
.venv311/Scripts/python.exe -m pytest -q
.venv311/Scripts/python.exe -m pip check
```

- Preserved CUDA environment: **98 tests passed**, dependency check passed,
  sources/tests compiled. The suite includes replay of all 42 published outputs
  against exact fixture hashes, TRAIN records and literal evidence.
- Minimal `.runtime/ci-env` with only `.[test]`: **98 tests passed** and dependency
  check passed; tests require no model download, torch or voice packages.
- **113 version pins plus `en_core_web_sm==3.8.0`** still match Mission 001 (114 total).
- The existing public CLI also generated seven validated synthetic Backend
  questions per mode on first attempts: lexical **17.198 s**, BGE/FAISS **16.841 s**.
  Both saved outputs were revalidated. These are supplemental structural smoke
  checks, not additional qualitative approvals or part of the six-case timing sum.
  BGE CLI ran offline at the pinned revision, without alternate weights.
- GitHub CI must be checked against the exact pushed delivery SHA; the final
  handoff links that run. Earlier green CI is not evidence for a newer commit.

Changed files cover the generator/demo, generation/adapter/demo/CLI regressions,
this report and AI handoff documentation, and three synthetic evidence artifacts.
`AGENTS.md`, both original environments, the small-model assets, dependency lock,
nested clone, frontend, backend and `main` were preserved. No Prometheus download,
fine-tuning, external dataset scraping, private CV, audio, cache or weight commit occurred.

The next engineering task is to close the open semantic-citation and reference
quality gate with independently reviewed criteria and held-out cases. Then hand
the typed generator to Oussema's FastAPI service with timeout/error/observability
tests. Keep scoring unconfigured at HTTP 501 until reviewed references and
calibration exist. End-to-end frontend/backend integration remains separate work.
