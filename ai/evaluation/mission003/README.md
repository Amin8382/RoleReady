# Mission 003 evaluation assets

`retrieval_queries.jsonl` contains 32 agent-authored search needs across eight
roles. They are queries, **not searchable corpus documents**. They were authored
before inspecting their ranked results. Role-family expansion is search policy,
not an invented publisher role annotation.

Real ranking/pool files live locally under
`ai/data/mission003/retrieval_runs/run-002/`, tracked by DVC. The CSV pool contains
the query, document ID, original question and source revision for review. Keep
human annotations in a separate file; do not overwrite the unjudged pool.

Relevance grades: 0 = does not address the requested competency; 1 = tangential
or partial; 2 = substantially relevant; 3 = directly addresses the need. These are
instructions for reviewers, not claims that source difficulty/roles are correct.
Read the full question: keyword/domain overlap can conceal an irrelevant or
technically confused scenario. Review both systems' pooled documents, including
nonrelevant ones, rather than approving only a preferred retriever's examples.

`provisional_judgments.json` contains explicitly provisional agent observations
for selected actual results. It is incomplete, has no human reviewer approvals
and cannot produce official quality metrics. Empty/partial pools cannot establish
that no relevant document exists anywhere in the corpus.

For a human review, copy the pool CSV to a private working file, grade each pair,
set `label_status=human_reviewed`, and record a reviewer identifier and review date.
The importer approves a query pool only when **all** of that pool's rows have
explicit approvals. Human identity is declared, not cryptographically authenticated.
Do not commit private reviewer details or private evaluation material.

From `ai/`:

```powershell
.venv311/Scripts/python.exe -m roleready_ai.retrieval_evaluation import-review --pool data/mission003/retrieval_runs/run-002/judgments.unjudged.json --csv data/private/review.csv --out data/private/judgments.reviewed.json
.venv311/Scripts/python.exe -m roleready_ai.retrieval_evaluation metrics --rankings data/mission003/retrieval_runs/run-002/rankings.json --judgments data/private/judgments.reviewed.json
```

P@5 uses denominator 5 (missing results get no credit). Recall@5/@10 uses the
assessed positive set, grade >0. MRR@10 is reciprocal rank of the first positive
within ten results. nDCG@10 uses gain `2^grade - 1` and discount `log2(rank+1)`.
Recall/nDCG remain **pool-relative**, not exhaustive corpus-wide ground truth.
Report reviewed-query coverage and label limitations alongside any future metrics.
Currently no genuine human-reviewed relevance judgments are available; official
P@5, Recall@5/@10, MRR@10 and nDCG@10 are withheld. Do not claim quality superiority.

Generation scenarios are separately stored in `examples/mission003/`; they never
enter the corpus or future supervised training. The one predeclared generation
comparison uses no retrieval, lexical retrieval and persisted BGE retrieval.
Raw technical criteria remain unreviewed and unsuitable as scoring references.
The source benchmark's references/rubrics are research assets, not calibrated
RoleReady scores or independently verified answers.

`generation_evidence.agent.json` records the completed nine-case/63-question
batch, source/evidence checks, request times, sampled device memory and per-case
agent findings. It explicitly keeps the quality gate open. Three small, unedited
BGE output samples are in `examples/mission003/`; full prompts/attempts remain
ignored under `outputs/mission003/generation-run-001/`.

`source_audit.json`, `index_benchmark.json`, `retrieval_benchmark.json` and
`dvc_reproducibility.json` are lightweight metadata/evidence reports copied from
the actual local runs. They contain no corpus bodies or human approvals. Do not
edit their measurements to match expectations or substitute a unit-test fixture
for real inference. The broader interpretation and reproduction commands are in
`ai/docs/MISSION_003_DATASETS_AND_RAG.md`.
