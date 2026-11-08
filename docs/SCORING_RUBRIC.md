# RoleReady interview evaluation rubric v1.0

**Status:** proposed human-review rubric; not an active scored model or hiring prediction.

Use the candidate's corrected transcript as the evaluation input, retaining the original transcript for audit. Consider the actual question, evaluation criteria and job context. Evaluate on four dimensions, each **1–5**. Anchor scoring in specific answer excerpts.

| Score | Correctness | Coverage | Relevance | Evidence / structure |
| --- | --- | --- | --- | --- |
| 1 | Major errors / unsupported claims | Core requirements absent | Does not address prompt | No clear example or organization |
| 2 | Material errors | Few criteria addressed | Mostly off-topic | Vague or disorganized |
| 3 | Mostly sound with limitations | Important criteria partially met | Generally on-topic | Some concrete steps/example |
| 4 | Accurate, minor issues | Most relevant criteria addressed | Direct and contextualized | Clear actions, logic, outcomes |
| 5 | Accurate and well qualified | All relevant criteria addressed | Precise, tailored answer | Specific verifiable reasoning and outcomes |

For **behavioral** questions, weight structured, authentic examples and reflection; do not infer a candidate's character from style. For **technical** questions, correctness should be evaluated against human-reviewed reference criteria. If data are insufficient, mark *not assessable* instead of guessing. A missing answer may be marked unanswered, not as evidence of incompetence.

## Evaluation record required

`session_id`, `question_id`, `original_transcript`, `corrected_transcript`, `rubric_version`, 1–5 dimension ratings (when assessable), excerpts supporting each judgment, strengths, actionable improvements, `model_id`, `prompt_version`, `latency_ms`, and evaluator uncertainty.

## Validation plan

Recruit two independent reviewers for weak/partial/strong answer samples; reconcile the rubric first, then compare blind model ratings. Record reviewer disagreement, score distribution, category errors, hallucinated evidence, model version and calibration before exposing model scores in the UI. Treat any aggregate as a *practice* score only.
