"""Prometheus 2 official absolute-grading prompt format and strict parser.

This is a PRACTICE assessment, not a hiring predictor. A human-reviewed
reference answer is required: reference criteria alone are not a reference.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import re
import time
from typing import Protocol

from .chat import ChatEndpoint

DEFAULT_PROMETHEUS = "prometheus-eval/prometheus-7b-v2.0"
SYSTEM = (
    "You are a fair judge assistant tasked with providing clear, objective feedback "
    "based on specific criteria, ensuring each assessment reflects the absolute "
    "standards set for performance."
)
RUBRIC: dict[str, tuple[str, str, str, str, str]] = {
    "correctness": (
        "Major errors or unsupported claims.",
        "Material inaccuracies or insufficient accuracy.",
        "Mostly accurate with meaningful limitations.",
        "Accurate with only minor issues.",
        "Technically sound and well-qualified, no material errors.",
    ),
    "coverage": (
        "Does not address core criteria.",
        "Addresses only a small part of the expected answer.",
        "Partially covers important criteria.",
        "Covers most reference criteria.",
        "Covers all relevant reference criteria thoroughly.",
    ),
    "relevance": (
        "Does not answer the actual question.",
        "Mostly off topic.",
        "Generally answers the question with some drift.",
        "Directly answers the question in the given context.",
        "Precisely and consistently addresses the interview question.",
    ),
    "evidence_structure": (
        "No coherent example or structure.",
        "Very vague or disorganized.",
        "Some concrete reasoning or example.",
        "Clear reasoning, own actions and outcomes.",
        "Specific, credible evidence and an effective logical structure.",
    ),
}


class TextJudge(Protocol):
    model: str
    def complete(self, *, system: str, user: str, max_tokens: int = 1200) -> str: ...


@dataclass(frozen=True)
class CriterionScore:
    criterion: str
    score: int
    feedback: str


@dataclass(frozen=True)
class PracticeEvaluation:
    model_id: str
    rubric_version: str
    dimensions: list[CriterionScore]
    average_score_1_to_5: float
    latency_ms: int
    warning: str = (
        "Uncalibrated AI practice feedback; compare with human interview ratings. "
        "This is not a hiring likelihood or verified assessment."
    )


def absolute_prompt(*, question: str, answer: str, reference_answer: str, criterion: str) -> str:
    if criterion not in RUBRIC:
        raise ValueError("Unknown rubric dimension")
    if not all(value.strip() for value in (question, answer, reference_answer)):
        raise ValueError("Question, corrected answer and reviewed reference are required")
    desc = RUBRIC[criterion]
    lines = [
        "###Task Description:",
        "An instruction, a response to evaluate, a score-5 reference answer and a score rubric are given.",
        "1. Write detailed feedback based ONLY on this rubric.",
        "2. End with an integer between 1 and 5.",
        '3. Output: Feedback: (criterion-specific feedback) [RESULT] (an integer 1 to 5)',
        "4. Do not add anything after the score.",
        "",
        "###The instruction to evaluate:", question,
        "###Response to evaluate:", answer,
        "###Reference Answer (Score 5):", reference_answer,
        "###Score Rubrics:", f"[{criterion}]",
    ]
    lines.extend(f"Score {i}: {description}" for i, description in enumerate(desc, 1))
    lines += ["", "###Feedback:"]
    return "\n".join(lines)


def parse_absolute(text: str) -> tuple[int, str]:
    match = re.fullmatch(r"\s*(?:Feedback:\s*)?(.+?)\s*\[RESULT\]\s*([1-5])\s*", text, re.I | re.S)
    if match is None:
        raise ValueError("Prometheus response must end in [RESULT] followed by integer 1-5")
    feedback = match.group(1).strip()
    if not feedback:
        raise ValueError("Prometheus returned no feedback")
    return int(match.group(2)), feedback


class PrometheusEvaluator:
    def __init__(self, *, judge: TextJudge) -> None:
        self.judge = judge

    @classmethod
    def from_env(cls) -> "PrometheusEvaluator":
        base = os.environ.get("ROLEREADY_PROMETHEUS_BASE_URL", "")
        if not base:
            raise ValueError("Set ROLEREADY_PROMETHEUS_BASE_URL to a running /v1 endpoint")
        return cls(judge=ChatEndpoint(
            base_url=base,
            model=os.environ.get("ROLEREADY_PROMETHEUS_MODEL", DEFAULT_PROMETHEUS),
            api_key=os.environ.get("ROLEREADY_PROMETHEUS_API_KEY", ""),
        ))

    def evaluate(
        self, *,
        question: str,
        corrected_transcript: str,
        reviewed_reference_answer: str,
    ) -> PracticeEvaluation:
        if not question.strip() or not corrected_transcript.strip():
            raise ValueError("Question and corrected transcript are required")
        if not reviewed_reference_answer.strip():
            raise ValueError("A HUMAN-REVIEWED reference answer is mandatory")
        started = time.perf_counter()
        scores: list[CriterionScore] = []
        for criterion in RUBRIC:
            response = self.judge.complete(
                system=SYSTEM,
                user=absolute_prompt(
                    question=question,
                    answer=corrected_transcript,
                    reference_answer=reviewed_reference_answer,
                    criterion=criterion,
                ),
                max_tokens=1000,
            )
            score, feedback = parse_absolute(response)
            scores.append(CriterionScore(criterion=criterion, score=score, feedback=feedback))
        return PracticeEvaluation(
            model_id=self.judge.model,
            rubric_version="1.0",
            dimensions=scores,
            average_score_1_to_5=round(sum(item.score for item in scores) / len(scores), 2),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
