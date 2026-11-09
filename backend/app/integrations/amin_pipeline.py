"""
Teammate Interface Adapter: Mohamed Amin Guesmi (AI & Data Pipeline)
Provides concrete fallback stubs for Qwen 3.5 4B and FAISS retrieval.
When Amin deploys his live pipeline module, his functions plug in here directly.
"""

from typing import List, Dict, Any


def run_cv_job_analysis(cv_text: str, job_text: str) -> Dict[str, Any]:
    """
    STUB / INTERFACE for Amin's Qwen 3.5 4B model.
    Analyzes candidate CV against job requirements.
    """
    return {
        "strengths": [
            "Demonstrated core competency in Python programming and modular software design",
            "Practical background with data structures and API integrations",
            "Clear alignment with backend architecture requirements mentioned in job prompt",
        ],
        "requirements_not_evidenced": [
            "Large-scale distributed cluster deployment (Note: missing CV evidence does not prove a missing skill)",
            "High-throughput vector indexing benchmarks beyond single-node prototypes",
        ],
        "supporting_source_excerpts": [
            f"Job prompt extracts: '{job_text[:120]}...'",
            f"CV evidence extracts: '{cv_text[:120]}...'",
        ],
    }


def generate_seven_questions(
    target_role: str,
    experience_level: str,
    cv_text: str,
    job_text: str,
) -> List[Dict[str, Any]]:
    """
    STUB / INTERFACE for Amin's FAISS retrieval + Qwen 3.5 4B generator.
    Selects 7 distinct, tailored technical & behavioral questions.
    """
    return [
        {
            "question_id": "q1",
            "text": f"In your role as a {target_role}, how do you evaluate latency versus accuracy when deploying approximate nearest neighbor vector search?",
            "target_skill": "Vector Search & Retrieval Architecture",
            "difficulty": "medium",
            "reason_for_asking": "Job specifies scalable search; CV highlights single-node prototypes.",
            "reference_criteria": "Candidate should mention indexing trade-offs (e.g. IVF vs HNSW), product quantization (PQ), RAM footprint, and recall calibration.",
            "source_ids": ["ML_systems_interview_bench_01"],
        },
        {
            "question_id": "q2",
            "text": "How do you detect and prevent subtle data leakage between training, validation, and production inference pipelines?",
            "target_skill": "ML Pipeline Integrity & Validation",
            "difficulty": "medium",
            "reason_for_asking": "Crucial requirement for reproducible data systems.",
            "reference_criteria": "Mentions temporal splits, fitting transformers/scalers only on train fold, avoiding target feature contamination, and automated drift checks.",
            "source_ids": ["ML_interview_SFT_104"],
        },
        {
            "question_id": "q3",
            "text": "Describe how you design a resilient REST API with database transactions, rate limiting, and defensive input validation.",
            "target_skill": "Backend Engineering & Reliability",
            "difficulty": "medium",
            "reason_for_asking": "Job emphasizes production backend APIs handling unstructured inputs.",
            "reference_criteria": "Addresses idempotent operations, connection pooling, schema validation (e.g. Pydantic), and graceful error responses.",
            "source_ids": ["InterviewForge_SWE_210"],
        },
        {
            "question_id": "q4",
            "text": "When an LLM evaluation benchmark produces fluctuating or inconsistent scores, how do you diagnose and stabilize the scoring rubric?",
            "target_skill": "LLM-as-a-Judge Evaluation & Calibration",
            "difficulty": "hard",
            "reason_for_asking": "Directly tests evaluation methodologies relevant to RoleReady's scoring core.",
            "reference_criteria": "Discusses rubric anchored examples, temperature reduction, human rating correlation checks (Pearson/MAE), and majority voting.",
            "source_ids": ["RoleReady_Eval_Spec_03"],
        },
        {
            "question_id": "q5",
            "text": "Tell me about a technical disagreement you had with a teammate regarding system architecture, and how you reached a resolution.",
            "target_skill": "Technical Collaboration & Communication",
            "difficulty": "easy",
            "reason_for_asking": "Assesses behavioral collaboration using STAR methodology.",
            "reference_criteria": "Uses STAR method: outlines Situation, Task, Action with objective data/benchmarks, and positive outcome.",
            "source_ids": ["Behavioral_QuestionBank_12"],
        },
        {
            "question_id": "q6",
            "text": "How do you handle audio transcription latency and background noise degradation in real-time voice applications?",
            "target_skill": "Audio Processing & Streaming STT",
            "difficulty": "medium",
            "reason_for_asking": "Job targets end-to-end voice interview workflows.",
            "reference_criteria": "Covers chunked audio streaming, VAD (Voice Activity Detection), beam search vs greedy decoding, and client-side transcript correction.",
            "source_ids": ["Speech_Engineering_Bench_07"],
        },
        {
            "question_id": "q7",
            "text": "What strategies do you employ to monitor API health, memory leaks, and model drift in live deployment?",
            "target_skill": "Observability & Production Monitoring",
            "difficulty": "hard",
            "reason_for_asking": "Ensures candidate understands post-deployment lifecycle.",
            "reference_criteria": "Explains metrics (p95 latency, error rates), structured logging, alerting thresholds, and scheduled shadow evaluations.",
            "source_ids": ["DevOps_MLOps_Bench_19"],
        },
    ]


def generate_cheat_sheet(
    target_role: str,
    strengths: List[str],
    gaps: List[str],
    evaluations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    STUB / INTERFACE for Amin's Qwen 3.5 4B cheat sheet writer.
    Synthesizes interview preparation insights into actionable takeaways.
    """
    return {
        "key_strengths_summary": strengths or [
            "Solid core technical vocabulary across engineering concepts",
            "Clear and logical communication structure",
        ],
        "priority_improvements": [
            {
                "category": "Architectural Trade-offs",
                "gap_description": "Tendency to propose single solutions without explicitly contrasting memory vs latency trade-offs.",
                "action_item": "Practice structuring answers with 'Solution A vs Solution B' comparison before choosing.",
            },
            {
                "category": "Quantitative Rigor",
                "gap_description": "Answers occasionally lack concrete benchmark numbers and edge case considerations.",
                "action_item": "Incorporate specific metrics (e.g. p95 latency, memory footprints) in practice explanations.",
            },
        ],
        "key_technical_concepts": [
            "Approximate Nearest Neighbor (IVF, HNSW, Product Quantization)",
            "Data Leakage Prevention & Temporal Splits",
            "LLM-as-a-Judge Calibration & Correlation",
            "Graceful Degradation & Timeout Resiliency",
        ],
        "recommended_answer_structures": [
            "STAR Method (Situation, Task, Action, Result) for behavioral answers",
            "Trade-Off Analysis (Requirement -> Alternatives -> Bottlenecks -> Chosen approach) for systems",
        ],
        "suggested_next_practice_steps": [
            "Re-attempt question 1 with emphasis on quantization RAM calculations",
            "Run through question 4 with specific human evaluation anchor examples",
        ],
    }

