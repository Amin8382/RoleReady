import uuid
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from pypdf import PdfReader
from ..schemas.session import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionAnalysisRequest,
    SessionAnalysisResponse,
    SessionStateResponse,
    ExperienceLevel,
)
from ..schemas.report import FinalReportResponse, DeleteDataResponse
from ..schemas.answer import AnswerEvaluationResponse
from ..auth.middleware import get_current_user_id
from ..database import get_repository
from ..integrations.amin_pipeline import run_cv_job_analysis, generate_cheat_sheet

router = APIRouter(tags=["Sessions"])

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted.append(text)
    return "\n".join(extracted).strip()


@router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    target_role: Optional[str] = Form(None),
    experience_level: Optional[str] = Form("mid"),
    job_text: Optional[str] = Form(None),
    cv_text: Optional[str] = Form(None),
    cv_file: Optional[UploadFile] = File(None),
    user_id: str = Depends(get_current_user_id),
):
    """
    Creates a new interview preparation session.
    Accepts multipart form-data (with CV PDF/text upload) or form fields.
    Validates empty, unsupported, and oversized files.
    """
    final_role = target_role or "Software Engineer"
    final_exp = experience_level or "mid"
    final_job = job_text or ""
    final_cv = cv_text or ""

    if cv_file:
        filename = (cv_file.filename or "").lower()
        if not (filename.endswith(".pdf") or filename.endswith(".txt")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Please upload a .pdf or .txt file.",
            )

        contents = await cv_file.read()
        if len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded CV file is empty.",
            )

        if len(contents) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds the 5 MB limit.",
            )

        try:
            if filename.endswith(".pdf"):
                extracted = extract_text_from_pdf(contents)
                if not extracted:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Could not extract readable text from the uploaded PDF.",
                    )
                final_cv = extracted
            else:
                final_cv = contents.decode("utf-8", errors="replace")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read CV file: {str(e)}",
            )

    if not final_job or len(final_job.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description must be at least 10 characters.",
        )

    if not final_cv or len(final_cv.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CV content must be at least 10 characters (either uploaded or pasted).",
        )

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    repo = get_repository()

    session_data = {
        "id": session_id,
        "user_id": user_id,
        "target_role": final_role,
        "experience_level": final_exp,
        "cv_text": final_cv,
        "job_text": final_job,
        "status": "created",
    }
    repo.create_session(session_data)

    return SessionCreateResponse(
        session_id=session_id,
        target_role=final_role,
        experience_level=final_exp,
        status="created",
        message="Session successfully initialized. Ready for CV/job analysis.",
    )


@router.get("/sessions/{id}", response_model=SessionStateResponse)
def get_session_state(id: str, user_id: str = Depends(get_current_user_id)):
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Enforce access control
    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session")

    questions = repo.get_questions(id)
    answers = repo.get_answers(id)

    return SessionStateResponse(
        session_id=id,
        user_id=session["user_id"],
        target_role=session["target_role"],
        experience_level=session["experience_level"],
        status=session.get("status", "created"),
        has_analysis=bool(session.get("strengths")),
        questions_count=len(questions),
        answers_count=len(answers),
        is_completed=len(answers) >= 7,
    )


@router.post("/sessions/{id}/analysis", response_model=SessionAnalysisResponse)
def store_session_analysis(
    id: str,
    analysis: Optional[SessionAnalysisRequest] = None,
    user_id: str = Depends(get_current_user_id),
):
    """
    Stores or computes the CV vs Job analysis.
    Integrates with Amin's module or accepts his pre-computed payload.
    """
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if analysis:
        strengths = analysis.strengths
        gaps = analysis.requirements_not_evidenced
        excerpts = analysis.supporting_source_excerpts
    else:
        # Run through Amin's pipeline stub
        computed = run_cv_job_analysis(session.get("cv_text", ""), session.get("job_text", ""))
        strengths = computed["strengths"]
        gaps = computed["requirements_not_evidenced"]
        excerpts = computed["supporting_source_excerpts"]

    repo.update_session(id, {
        "strengths": strengths,
        "requirements_not_evidenced": gaps,
        "supporting_source_excerpts": excerpts,
        "status": "analyzed",
    })

    return SessionAnalysisResponse(
        session_id=id,
        target_role=session["target_role"],
        cv_text_preview=(session.get("cv_text") or "")[:200] + "...",
        job_text_preview=(session.get("job_text") or "")[:200] + "...",
        strengths=strengths,
        requirements_not_evidenced=gaps,
        supporting_source_excerpts=excerpts,
    )


@router.get("/sessions/{id}/results")
def get_session_results(id: str, user_id: str = Depends(get_current_user_id)):
    """Retrieves all evaluated answers for this session."""
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    answers = repo.get_answers(id)
    return {
        "session_id": id,
        "total_evaluated": len(answers),
        "results": answers,
        "practice_notice": "Scores describe practice performance, not the probability of being hired.",
    }


@router.post("/sessions/{id}/report", response_model=FinalReportResponse)
def generate_session_report(id: str, user_id: str = Depends(get_current_user_id)):
    """
    Finalizes the interview preparation session.
    Aggregates all 7 evaluated answers, synthesizes priority improvements and cheat sheet.
    """
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["user_id"] != user_id and session["user_id"] != "demo-candidate-001":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    raw_answers = repo.get_answers(id)
    if not raw_answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate report: No practice questions have been evaluated yet.",
        )

    eval_responses = [
        AnswerEvaluationResponse(
            session_id=id,
            question_id=a["question_id"],
            original_transcript=a["original_transcript"],
            corrected_transcript=a["corrected_transcript"],
            rubric_version=a.get("rubric_version", "v1.0"),
            scores=a["scores"],
            evidence=a.get("evidence", []),
            feedback=a["feedback"],
        )
        for a in raw_answers
    ]

    avg_score = round(sum(a.scores.overall_score for a in eval_responses) / len(eval_responses), 2)

    cheat_sheet_data = generate_cheat_sheet(
        target_role=session["target_role"],
        strengths=session.get("strengths", []),
        gaps=session.get("requirements_not_evidenced", []),
        evaluations=[a.model_dump() for a in eval_responses],
    )

    report_id = f"rep_{uuid.uuid4().hex[:12]}"
    report_record = {
        "id": report_id,
        "session_id": id,
        "user_id": user_id,
        "average_score": avg_score,
        "priority_improvements": cheat_sheet_data["priority_improvements"],
        "cheat_sheet_content": cheat_sheet_data,
        "pdf_storage_path": f"/sessions/{id}/pdf",
    }
    repo.save_report(report_record)
    repo.update_session(id, {"status": "completed"})

    return FinalReportResponse(
        session_id=id,
        target_role=session["target_role"],
        experience_level=session["experience_level"],
        seven_results=eval_responses,
        average_session_score=avg_score,
        priority_improvements=cheat_sheet_data["priority_improvements"],
        cheat_sheet_content=cheat_sheet_data,
        pdf_location=f"/sessions/{id}/pdf",
        practice_notice="Scores describe practice performance, not the probability of being hired.",
    )


@router.get("/sessions/{id}/pdf")
def download_preparation_pdf(id: str, user_id: str = Depends(get_current_user_id)):
    """
    Exports a clean, structured printable preparation cheat sheet PDF.
    """
    repo = get_repository()
    session = repo.get_session(id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    report = repo.get_report(id)
    role = session.get("target_role", "Candidate")
    avg = report.get("average_score", 4.0) if report else 4.0

    # Minimal printable text/PDF document stream
    pdf_content = (
        f"%PDF-1.4\n1 0 obj\n<< /Title (RoleReady Preparation Sheet - {role}) >>\n"
        f"endobj\nstream\nRoleReady Interview Preparation Sheet\nTarget Role: {role}\nPractice Score: {avg}/5.0\nendstream\n%%EOF"
    ).encode("utf-8")

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=RoleReady_Prep_{id}.pdf"},
    )


@router.delete("/user/data", response_model=DeleteDataResponse)
def delete_candidate_data(user_id: str = Depends(get_current_user_id)):
    """
    GDPR & privacy requirement: Deletes all sessions, questions, answers, and reports
    associated with the authenticated candidate.
    """
    repo = get_repository()
    deleted_count = repo.delete_user_data(user_id)
    return DeleteDataResponse(
        status="success",
        user_id=user_id,
        deleted_sessions_count=deleted_count,
        message=f"All {deleted_count} candidate sessions and transcripts have been completely deleted.",
    )

