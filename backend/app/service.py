"""Transparent, non-ML baseline only. Never present this as model output."""
import re
from uuid import uuid4
from .schemas import Analysis, InterviewQuestion, SessionRequest, SessionResponse, SkillEvidence

SKILLS = [
    "python", "sql", "typescript", "javascript", "react", "next.js", "fastapi", "pytorch",
    "tensorflow", "machine learning", "deep learning", "nlp", "rag", "llm", "docker",
    "kubernetes", "aws", "azure", "gcp", "postgresql", "git", "ci/cd", "rest api",
    "data analysis", "statistics", "scikit-learn", "pandas", "spark", "transformers", "faiss",
]

def excerpt(text: str, skill: str) -> str | None:
    match = re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", text, flags=re.I)
    if match is None:
        return None
    start, end = max(0, match.start() - 75), min(len(text), match.end() + 75)
    return text[start:end].replace("\n", " ").strip()

def build_session(data: SessionRequest) -> SessionResponse:
    strengths: list[SkillEvidence] = []
    missing: list[SkillEvidence] = []
    for skill in SKILLS:
        job_excerpt = excerpt(data.job_description, skill)
        if job_excerpt is None:
            continue
        cv_excerpt = excerpt(data.cv_text, skill)
        evidence = SkillEvidence(requirement=skill, job_excerpt=job_excerpt, cv_excerpt=cv_excerpt)
        (strengths if cv_excerpt is not None else missing).append(evidence)

    primary_gap = missing[0].requirement if missing else "an unfamiliar requirement"
    primary_strength = strengths[0].requirement if strengths else "your strongest project skill"
    role = data.target_role
    prompts = [
        ("motivation", f"Tell me about yourself and why you want to work as a {role}.", "Assess motivation and role alignment.", ["Specific experience", "Role motivation"]),
        ("project", f"Describe the project that best prepares you for a {role} position.", "Connect CV evidence to the target job.", ["Personal contribution", "Challenges", "Outcome"]),
        ("growth", f"The role calls for {primary_gap}. How would you approach a task that needs it?", "Explore a requirement not evidenced in the CV, without assuming absence of skill.", ["Honest skill level", "Learning plan", "Concrete steps"]),
        ("technical", f"Walk me through a concrete example of how you used {primary_strength}.", "Assess real, specific technical or project evidence.", ["Context", "Own decisions", "Result"]),
        ("collaboration", "Tell me about a disagreement on a team and how you resolved it.", "Examine communication under pressure.", ["Context", "Action", "Outcome"]),
        ("problem-solving", "Describe a difficult problem where your first approach did not work.", "Examine adaptability and reasoning.", ["Failure mode", "Revised approach", "Learning"]),
        ("role-readiness", f"What would you prioritize in your first 30 days as a {role}?", "Assess understanding of the work and learning priorities.", ["Priorities", "Stakeholder alignment", "Measurable goals"]),
    ]
    level = "easy" if data.experience_level in {"entry", "junior"} else "medium" if data.experience_level == "mid" else "hard"
    questions = [InterviewQuestion(
        question_id=f"q{idx}", text=text, target_skill=skill, difficulty=level,
        reason_for_asking=reason, reference_criteria=criteria, source_ids=[]
    ) for idx, (skill, text, reason, criteria) in enumerate(prompts, 1)]
    return SessionResponse(
        session_id=str(uuid4()), target_role=role, experience_level=data.experience_level,
        analysis=Analysis(
            strengths=strengths, requirements_not_evidenced=missing,
            note="Keyword evidence only. Missing text in a CV does not mean the candidate lacks the skill."
        ),
        questions=questions,
    )
