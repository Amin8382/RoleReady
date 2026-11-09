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
prevents invented/combined quotes without silently rewriting model responses.
The rationale ends with a fixed neutral uncertainty statement, rather than a
free-form conclusion about candidate ability. First-person prefixes, some
unsupported-incident phrases, deficit labels and past-action criteria are rejected.
These are conservative heuristics, not a complete semantic-factuality validator.
CLI outputs explicitly carry `quality_status=unreviewed_model_output`.
Requirements not evidenced by the CV must lead to hypothetical questions rather
than invented prior experience or missing-ability judgments.

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

## Actual artifact, endpoint and measurements

| Item | Verified value |
| --- | --- |
| Source artifact | `qwen3.5:4b-q4_K_M`, GGUF Q4_K_M, reported 4.2B |
| Source package bytes | 3,324,173,934 |
| Source manifest SHA-256 | `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` |
| Served model | `roleready-qwen35-4b:8k` |
| Profile manifest SHA-256 | `27af9727272c8f96be4302b0283fa045132389692e9c86949081d18484d1cfb8` |
| Tested question endpoint | `http://127.0.0.1:11434/v1/chat/completions` |
| Server/runner | Existing Ollama 0.40.15 / `llamacpp`, Windows |
| Placement | `ollama ps`: 100% GPU; context 8192; only this profile loaded |
| Model GPU allocation from `/api/ps` | 3,364,911,840 bytes (about 3209 MiB) |
| Whole GPU cold baseline / sampled peak | 1680 / 5736 MiB used |
| Final RAG whole-device sampled peaks | 5801-6185 MiB used; GPU utilization peaks 75-93% |

The first real short response explained a REST API in English. Its client wall
time was **201.201 s**: native server metrics reported **103.352 s loading**,
**92.261 s prompt evaluation**, and **5.556 s decoding** for 33 generated tokens.
This cold observation includes initialization; it must not be presented as steady
inference speed. A later warm short call took **0.952 s** wall time, with
**11.333 ms loading**, **312.712 ms prompt evaluation** and **345.233 ms decoding**
for 28 generated tokens. No reasoning text was returned in either call.

The original language and projector layers were reused by the serving profile:
`a9d0a3e1d8c91732a3812becd31f8d4a8ff57414903f226306069f0437e2ac50`
and `e56a899b1540860385465756dd308c84417410b94dbc1c380adffd20a921ca60`.
The profile's different manifest represents serving parameters, not different weights.

## Final six-case result

Final recorded directory: `ai/outputs/qwen-mission002/attempt-07/`.

| Synthetic scenario | Lexical latency | BGE/FAISS latency | Valid questions per mode |
| --- | ---: | ---: | --- |
| Junior Data Analyst | 17.616 s | 13.157 s | 7 / 7 |
| Machine Learning Engineer | 14.367 s | 13.215 s | 7 / 7 |
| Backend Developer | 14.721 s | 15.811 s | 7 / 7 |

All six passed strict JSON, exact count/fields/types, source membership, literal
CV/job evidence and duplicate/wording checks on **attempt one**, with
`finish_reason=stop` and zero returned reasoning characters. All 42 questions
were revalidated before export. No semantic-similarity pair reached the heuristic
0.86 threshold; final maximum pair scores ranged from 0.71502 to 0.76352.
Some questions remain generic and some evidence-to-question links are weak.
Both retrievers selected the same eight role-compatible records in this small
bank, in different orders: this demonstrates both integrations, not that BGE is
better than lexical retrieval.

Reviewable, unedited outputs and actual retrieved text/IDs are in
[`synthetic_samples.json`](../evaluation/mission002/synthetic_samples.json).
Exact timings, token counts, GPU metrics and run history are in
[`runtime_summary.json`](../evaluation/mission002/runtime_summary.json).
The raw prompts/attempt logs stay local and ignored. Examples from the final run:

- Data Analyst / lexical / `syn-da-dashboard`: "How would you design a dashboard
  that effectively communicates complex sales metrics to nontechnical stakeholders?"
- ML Engineer / lexical / `syn-ml-api`: "How would you test and version a machine
  learning inference API?"
- Backend / lexical / `syn-be-concurrency`: "How would you prevent two concurrent
  requests from booking the same appointment to ensure data integrity?"

## Failures retained and quality findings

| Recorded run | Outcome and response |
| --- | --- |
| attempt-01 | Short real inference passed; BGE setup stopped because an offline full-repository snapshot expected unneeded ONNX/bin files. Fixed by requesting only the Mission 001 cached subset. |
| attempt-02 | 0/6 accepted after two attempts each: free-form reasons ignored the literal-evidence format. All raw responses retained. |
| attempt-03 | 2/6 accepted: format was enforced, but copied evidence still added words or combined noncontiguous clauses. |
| attempt-04 | 6/6 structurally valid; agent inspection rejected first-person questions and unsupported deficit claims in free-form reasons. |
| attempt-05 | 6/6 structurally valid; inspection found an implied undocumented slow-query incident and past-action assumptions in criteria. |
| attempt-06 | 6/6 structurally valid; inspection found a remaining "lack of production monitoring experience" assertion. Added a regression/guard. |
| attempt-07 | 6/6 passed current automated checks on first attempts. Exported with explicit unreviewed quality status and agent findings. |

**Do not use the generated criteria as reviewed scoring references.** Agent
inspection of the final ML/BGE q4 criterion found "beyond those tested in the
course project", which presumes monitoring-signal testing absent from the CV.
This specific criterion is explicitly marked **not approved for scoring** in the
sample's review findings. Other criteria can be vague, prescriptive or shift
between hypothetical and past-tense expectations. Literal quotes and allowed
citation IDs do not solve semantic entailment; automated checks do not establish
technical accuracy, relevance or complete factuality. These limitations are
reported rather than calling the samples quality-validated.

The existing public CLI was also exercised with the synthetic backend session:
lexical produced seven validated questions in **19.313 s**, BGE/FAISS in
**21.987 s**, each on the first attempt. The first offline BGE CLI attempt failed
because no unversioned `main` cache ref existed. The standard retriever now pins
the exact verified BGE revision; the fixed CLI succeeded with Hub offline mode,
without downloading alternate weights. Both saved outputs were independently
revalidated. BGE's automatic device selection in the public CLI differs from
the demo's explicitly CPU embedding configuration; do not directly compare timings.

## Validation and handoff

- Preserved CUDA environment: **73 tests passed**, `pip check` passed, sources compiled.
- Fresh `.runtime/ci-env` with only `.[test]`: **73 tests passed**, dependency check passed;
  no torch, sentence-transformers or voice packages were installed there.
- All **114 Mission 001 pinned dependencies** still matched their recorded versions.
- No Prometheus weights, fine-tuning, external dataset scraping or private CVs were used.
- `AGENTS.md`, the original environment, small-model assets and nested clone were preserved.

Mission 003 should add a semantic-grounding/reference review gate and wire this
generator into Oussema's FastAPI contracts with timeout/error/observability tests.
Keep unconfigured scoring at HTTP 501. Build independently reviewed references
and held-out two-reviewer evaluations before Prometheus scoring or claims of
question-quality validation. The frontend-to-backend product remains unwired.
