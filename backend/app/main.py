"""FastAPI contract service. Model scoring is deliberately not simulated."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import AnswerEvaluationRequest, SessionRequest, SessionResponse
from .service import build_session

app = FastAPI(title="RoleReady API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "keyword_baseline"}

@app.post("/api/v1/sessions", response_model=SessionResponse)
def create_session(data: SessionRequest) -> SessionResponse:
    return build_session(data)

@app.post("/api/v1/evaluations")
def evaluate_answer(data: AnswerEvaluationRequest) -> None:
    raise HTTPException(status_code=501, detail={
        "code": "MODEL_NOT_CONFIGURED",
        "message": "Rubric-based scoring requires an evaluated and configured model. No score is invented in baseline mode.",
        "rubric_version": data.rubric_version,
    })
