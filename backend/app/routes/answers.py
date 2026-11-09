import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.answer import AnswerSubmitRequest, AnswerEvaluationResponse
from ..auth.middleware import get_current_user_id
from ..database import get_repository
from ..scoring.factory import get_scorer

router = APIRouter(tags=["Answers & Scoring"])


@router.post("/sessions/{id}/answers", response_model=AnswerEvaluationResponse)
async def submit_candidate_answer(
    id: str,
    payload: AnswerSubmitRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Submits candidate's answer (Whisper raw transcript + user corrected transcript).
    Triggers Prometheus 7B scoring against the question's reference criteria.
    Saves scores and actionable feedback to the database.
    """
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    questions = repo.get_questions(id)
    target_question = next((q for q in questions if q["question_id"] == payload.question_id), None)
    if not target_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{payload.question_id}' not found for this session.",
        )

    scorer = get_scorer()
    try:
        evaluation = await scorer.evaluate_answer(
            session_id=id,
            question_id=payload.question_id,
            question_text=target_question["text"],
            target_skill=target_question["target_skill"],
            reference_criteria=target_question["reference_criteria"],
            original_transcript=payload.original_transcript,
            corrected_transcript=payload.corrected_transcript,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scoring engine error: {str(e)}",
        )

    # Persist evaluation result
    answer_id = f"ans_{uuid.uuid4().hex[:12]}"
    answer_record = {
        "id": answer_id,
        "session_id": id,
        "question_id": payload.question_id,
        "user_id": user_id,
        "original_transcript": payload.original_transcript,
        "corrected_transcript": payload.corrected_transcript,
        "rubric_version": evaluation.rubric_version,
        "scores": evaluation.scores.model_dump(),
        "evidence": evaluation.evidence,
        "feedback": evaluation.feedback,
    }
    repo.save_answer(answer_record)

    return evaluation

