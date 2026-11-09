from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.question import QuestionRecord, QuestionsCreateRequest, QuestionsResponse
from ..auth.middleware import get_current_user_id
from ..database import get_repository
from ..integrations.amin_pipeline import generate_seven_questions

router = APIRouter(tags=["Questions"])


@router.get("/sessions/{id}/questions", response_model=QuestionsResponse)
def get_session_questions(id: str, user_id: str = Depends(get_current_user_id)):
    """
    Retrieves the 7 questions for this session.
    If questions have not yet been generated/stored, automatically invokes
    Amin's question generator to prepare the 7 questions.
    """
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    questions = repo.get_questions(id)
    if not questions:
        # Generate 7 tailored questions using Amin's pipeline stub
        generated = generate_seven_questions(
            target_role=session["target_role"],
            experience_level=session["experience_level"],
            cv_text=session.get("cv_text", ""),
            job_text=session.get("job_text", ""),
        )
        questions = repo.save_questions(id, user_id, generated)
        repo.update_session(id, {"status": "in_progress"})

    records = [
        QuestionRecord(
            question_id=q["question_id"],
            text=q["text"],
            target_skill=q["target_skill"],
            difficulty=q.get("difficulty", "medium"),
            reason_for_asking=q["reason_for_asking"],
            reference_criteria=q["reference_criteria"],
            source_ids=q.get("source_ids", []),
        )
        for q in questions
    ]

    return QuestionsResponse(
        session_id=id,
        total_questions=len(records),
        questions=records,
    )


@router.post("/sessions/{id}/questions", response_model=QuestionsResponse)
def save_custom_session_questions(
    id: str,
    payload: QuestionsCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Allows Amin's module or direct batch submission of 7 curated questions.
    """
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    q_dicts = [q.model_dump() for q in payload.questions]
    saved = repo.save_questions(id, user_id, q_dicts)
    repo.update_session(id, {"status": "in_progress"})

    return QuestionsResponse(
        session_id=id,
        total_questions=len(saved),
        questions=[QuestionRecord(**item) for item in saved],
    )
