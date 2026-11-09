import re
import json
import logging
from typing import Dict, Any, List, Optional
import httpx
from .interface import BaseScorer
from .mock_scorer import MockScorer
from ..schemas.answer import AnswerEvaluationResponse, RubricScores

logger = logging.getLogger(__name__)


PROMETHEUS_RUBRIC_TEMPLATE = """###Task Description:
An instruction (question), reference criteria for an ideal response, a candidate's practice transcript, and a score rubric (1-5 scale) are provided.
Your task is to evaluate the response across four key dimensions: Correctness, Coverage, Relevance, and Evidence/Structure.
Provide a clear breakdown with evidence snippets, specific actionable feedback, and score integers between 1 and 5.

###The instruction to evaluate:
{question_text}

###Target Skill:
{target_skill}

###Reference Criteria:
{reference_criteria}

###Candidate Response:
{candidate_answer}

###Score Rubric:
[Correctness]: 1 (severe factual error) to 5 (exemplary technical accuracy)
[Coverage]: 1 (omits all key criteria) to 5 (thoroughly covers all expected anchors)
[Relevance]: 1 (off-topic) to 5 (laser-focused)
[Evidence and Structure]: 1 (unsupported assertion) to 5 (masterful structure & trade-offs)

###Feedback format:
Scores:
- Correctness: [score 1-5]
- Coverage: [score 1-5]
- Relevance: [score 1-5]
- Evidence and Structure: [score 1-5]
Evidence:
- [quote or observation 1]
- [quote or observation 2]
Feedback: [concise constructive improvement points]
"""


class PrometheusScorer(BaseScorer):
    """
    Evaluates responses using Prometheus 7B v2 running on Ollama, vLLM, or HuggingFace endpoints.
    Includes robust regex parsing, retry handling, timeouts, and transparent fallback to MockScorer.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/api/generate",
        model_name: str = "prometheus-eval:7b-v2",
        timeout_seconds: float = 45.0,
        api_key: Optional[str] = None,
        fallback_on_error: bool = True,
    ):
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.fallback_on_error = fallback_on_error
        self.mock_fallback = MockScorer()

    def build_prompt(self, question: str, target_skill: str, reference_criteria: str, answer: str) -> str:
        return PROMETHEUS_RUBRIC_TEMPLATE.format(
            question_text=question,
            target_skill=target_skill,
            reference_criteria=reference_criteria,
            candidate_answer=answer,
        )

    def parse_prometheus_output(self, raw_text: str) -> Dict[str, Any]:
        """
        Extracts dimension scores, evidence bullets, and feedback text using regex.
        Handles variations in model formatting.
        """
        def extract_score(pattern: str, default: int = 3) -> int:
            m = re.search(pattern, raw_text, re.IGNORECASE)
            if m:
                try:
                    val = int(m.group(1))
                    return max(1, min(5, val))
                except (ValueError, TypeError):
                    pass
            return default

        correctness = extract_score(r"Correctness[:\s\-*]+(\d)", 3)
        coverage = extract_score(r"Coverage[:\s\-*]+(\d)", 3)
        relevance = extract_score(r"Relevance[:\s\-*]+(\d)", 3)
        structure = extract_score(r"Evidence(?:\s+and\s+Structure)?[:\s\-*]+(\d)", 3)

        # Extract Evidence bullets
        evidence_list = []
        evidence_match = re.search(r"Evidence:\s*\n((?:[-*•]\s*[^\n]+\n*)+)", raw_text, re.IGNORECASE)
        if evidence_match:
            lines = evidence_match.group(1).strip().split("\n")
            for line in lines:
                cleaned = re.sub(r"^[-*•]\s*", "", line).strip()
                if cleaned:
                    evidence_list.append(cleaned)
        if not evidence_list:
            evidence_list = ["Analysis based on reference criteria alignment."]

        # Extract Feedback
        feedback_match = re.search(r"Feedback:\s*([^\n]+(?:\n[^\n]+)*)", raw_text, re.IGNORECASE)
        feedback = feedback_match.group(1).strip() if feedback_match else "Focus on deepening technical trade-offs and providing concrete architectural details."

        overall = round((correctness + coverage + relevance + structure) / 4.0, 2)

        return {
            "correctness": correctness,
            "coverage": coverage,
            "relevance": relevance,
            "evidence_and_structure": structure,
            "overall_score": overall,
            "evidence": evidence_list,
            "feedback": feedback,
        }

    async def evaluate_answer(
        self,
        session_id: str,
        question_id: str,
        question_text: str,
        target_skill: str,
        reference_criteria: str,
        original_transcript: str,
        corrected_transcript: str,
    ) -> AnswerEvaluationResponse:
        prompt = self.build_prompt(question_text, target_skill, reference_criteria, corrected_transcript)

        # Ollama payload format
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 512},
        }

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data.get("response") or data.get("generated_text") or str(data)
                    parsed = self.parse_prometheus_output(raw_text)

                    return AnswerEvaluationResponse(
                        session_id=session_id,
                        question_id=question_id,
                        original_transcript=original_transcript,
                        corrected_transcript=corrected_transcript,
                        rubric_version="v1.0-prometheus",
                        scores=RubricScores(
                            correctness=parsed["correctness"],
                            coverage=parsed["coverage"],
                            relevance=parsed["relevance"],
                            evidence_and_structure=parsed["evidence_and_structure"],
                            overall_score=parsed["overall_score"],
                        ),
                        evidence=parsed["evidence"],
                        feedback=parsed["feedback"],
                        practice_notice="Scores describe practice performance on this attempt, not the probability of being hired.",
                    )
                else:
                    logger.warning(f"Prometheus endpoint returned status {response.status_code}: {response.text}")
                    if not self.fallback_on_error:
                        raise RuntimeError(f"Prometheus 7B upstream error: {response.status_code}")
        except Exception as e:
            logger.warning(f"Prometheus 7B unreachable ({e}). Using MockScorer fallback.")
            if not self.fallback_on_error:
                raise RuntimeError(f"Prometheus 7B service unavailable: {e}")

        # Fallback to MockScorer
        return await self.mock_fallback.evaluate_answer(
            session_id=session_id,
            question_id=question_id,
            question_text=question_text,
            target_skill=target_skill,
            reference_criteria=reference_criteria,
            original_transcript=original_transcript,
            corrected_transcript=corrected_transcript,
        )
