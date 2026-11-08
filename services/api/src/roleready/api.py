"""RoleReady API. Run bound to loopback behind the Next.js same-origin proxy."""

import asyncio
import hmac
import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from roleready.documents import build_report, extract_text, render_pdf
from roleready.engine import Engine
from roleready.schemas import AnswerInput, QuestionInput, ServiceError, SessionInput
from roleready.settings import Settings
from roleready.storage import Actor, LocalStore, SupabaseStore, now
from roleready.tracking import experiment
from roleready.voice import Voice

log = logging.getLogger("roleready")


async def authenticate(request: Request) -> Actor:
    settings = request.app.state.settings
    authorization = request.headers.get("authorization", "")
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    if settings.auth_mode == "local":
        if not token or not hmac.compare_digest(token, settings.local_token):
            raise ServiceError("unauthorized", "A local workspace token is required.", 401)
        return Actor("local-workspace")
    if not token:
        raise ServiceError("unauthorized", "Sign in to continue.", 401)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                settings.supabase_url.rstrip("/") + "/auth/v1/user",
                headers={"apikey": settings.supabase_anon_key, "Authorization": authorization},
            )
        if response.status_code in (401, 403):
            raise ServiceError("unauthorized", "Your sign-in expired. Please sign in again.", 401)
        response.raise_for_status()
        owner = str(UUID(response.json()["id"]))
        return Actor(owner, token)
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise ServiceError("auth_unavailable", "Sign-in verification is unavailable. Please retry.") from exc


def question_from(item, qid):
    question = next((q for q in item["analysis"]["questions"] if q["id"] == qid), None)
    if question is None:
        raise ServiceError("question_not_found", "This question does not belong to the session.", 404)
    return question


def create_app(settings=None, engine=None, store=None, voice=None):
    settings = settings or Settings()
    app = FastAPI(title="RoleReady", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine or Engine(settings)
    app.state.store = store or (
        SupabaseStore(settings.supabase_url, settings.supabase_anon_key)
        if settings.auth_mode == "supabase"
        else LocalStore(settings.state_dir / "sessions.db")
    )
    app.state.voice = voice or Voice(settings.voice_enabled)

    @app.middleware("http")
    async def request_policy(request: Request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 10 * 1024 * 1024:
            return JSONResponse(
                {"code": "request_too_large", "message": "Request exceeds the 10 MB limit."}, status_code=413
            )
        # Also cap chunked requests before the multipart parser can spool them.
        if request.method in ("POST", "PUT", "PATCH"):
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 10 * 1024 * 1024:
                    return JSONResponse(
                        {"code": "request_too_large", "message": "Request exceeds the 10 MB limit."},
                        status_code=413,
                    )
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ServiceError)
    async def service_error(_request, exc):
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        fields = [".".join(str(v) for v in error["loc"]) for error in exc.errors()]
        return JSONResponse(
            {"code": "invalid_input", "message": "Please check: " + ", ".join(fields)}, status_code=422
        )

    @asynccontextmanager
    async def measured(name):
        started, succeeded = time.perf_counter(), False
        try:
            yield
            succeeded = True
        finally:
            duration = time.perf_counter() - started
            if settings.track_api_metrics:

                def record():
                    try:
                        with experiment(
                            name,
                            {
                                "mode": settings.question_mode,
                                "generator": settings.generation_model,
                                "evaluator": settings.evaluation_model,
                            },
                            export=False,
                        ) as run:
                            run.metrics({"request_seconds": duration, "succeeded": int(succeeded)})
                            if not succeeded:
                                raise RuntimeError("Operation did not complete")
                    except Exception:
                        # Never serialize exception bodies or candidate content into logs.
                        log.info(
                            "Request metric recording finished with a failure outcome or unavailable tracker"
                        )

                await asyncio.to_thread(record)

    @app.get("/health")
    async def health():
        return {"service": "roleready", "status": "ok"}

    @app.get("/v1/capabilities")
    async def capabilities():
        return {
            "auth_mode": settings.auth_mode,
            "question_mode": settings.question_mode,
            "generator_configured": bool(settings.generation_url),
            "evaluator_configured": bool(settings.evaluation_url),
            "voice_enabled": settings.voice_enabled,
            "retriever": settings.retriever,
            "bank_prepared": (settings.data_root / "data/processed/bank.jsonl").exists(),
            "index_prepared": (settings.data_root / "data/index/questions.faiss").exists(),
            "notice": "Configuration status does not verify model availability or quality.",
        }

    @app.post("/v1/extract")
    async def extract(file: UploadFile = File(...), actor: Actor = Depends(authenticate)):
        content = await file.read(5 * 1024 * 1024 + 1)
        await file.close()
        return {"text": await asyncio.to_thread(extract_text, file.filename or "", content)}

    @app.get("/v1/sessions")
    async def sessions(actor: Actor = Depends(authenticate)):
        return await app.state.store.list(actor)

    @app.post("/v1/sessions", status_code=201)
    async def create_session(inputs: SessionInput, actor: Actor = Depends(authenticate)):
        async with measured("session-generation"):
            analysis = await app.state.engine.analyze(inputs)
            item = {
                "id": str(uuid4()),
                "version": 1,
                "created_at": now(),
                "inputs": inputs.model_dump(),
                "mode": settings.question_mode,
                "analysis": analysis.model_dump(),
                "answers": {},
                "drafts": {},
                "report": None,
            }
            await app.state.store.create(actor, item)
            return item

    @app.get("/v1/sessions/{session_id}")
    async def session(session_id: UUID, actor: Actor = Depends(authenticate)):
        return await app.state.store.get(actor, str(session_id))

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: UUID, actor: Actor = Depends(authenticate)):
        await app.state.store.delete(actor, str(session_id))
        return Response(status_code=204)

    @app.post("/v1/sessions/{session_id}/answers")
    async def answer(session_id: UUID, body: AnswerInput, actor: Actor = Depends(authenticate)):
        item = await app.state.store.get(actor, str(session_id))
        question = question_from(item, body.question_id)
        async with measured("answer-evaluation"):
            evaluation = await app.state.engine.score(question, body.transcript)
            original = item["drafts"].get(body.question_id, {}).get("original_transcript")
            item["answers"][body.question_id] = {
                "transcript": body.transcript,
                "original_transcript": original,
                "evaluation": evaluation.model_dump(),
                "submitted_at": now(),
            }
            item["report"] = None
            await app.state.store.save(actor, item, item["version"])
            return item

    @app.post("/v1/sessions/{session_id}/transcribe")
    async def transcribe(
        session_id: UUID,
        question_id: str = Form(...),
        file: UploadFile = File(...),
        actor: Actor = Depends(authenticate),
    ):
        item = await app.state.store.get(actor, str(session_id))
        question_from(item, question_id)
        content = await file.read(8 * 1024 * 1024 + 1)
        await file.close()
        if len(content) > 8 * 1024 * 1024:
            raise ServiceError("audio_size", "Audio must be smaller than 8 MB.", 413)
        async with measured("answer-transcription"):
            text = await asyncio.to_thread(app.state.voice.transcribe, content)
            item["drafts"][question_id] = {"original_transcript": text}
            await app.state.store.save(actor, item, item["version"])
            return {"transcript": text, "session": item}

    @app.post("/v1/sessions/{session_id}/speech")
    async def speech(session_id: UUID, body: QuestionInput, actor: Actor = Depends(authenticate)):
        item = await app.state.store.get(actor, str(session_id))
        question = question_from(item, body.question_id)
        async with measured("question-speech"):
            data = await asyncio.to_thread(app.state.voice.speak, question["text"])
            return Response(data, media_type="audio/wav")

    @app.post("/v1/sessions/{session_id}/report")
    async def report(session_id: UUID, actor: Actor = Depends(authenticate)):
        item = await app.state.store.get(actor, str(session_id))
        item["report"] = build_report(item)
        await app.state.store.save(actor, item, item["version"])
        return item

    @app.get("/v1/sessions/{session_id}/report.pdf")
    async def pdf(session_id: UUID, actor: Actor = Depends(authenticate)):
        item = await app.state.store.get(actor, str(session_id))
        if item["report"] is None:
            raise ServiceError("report_missing", "Create the cheat sheet first.", 409)
        data = await asyncio.to_thread(render_pdf, item["report"])
        return Response(
            data,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="RoleReady-cheat-sheet.pdf"'},
        )

    return app


app = create_app()
