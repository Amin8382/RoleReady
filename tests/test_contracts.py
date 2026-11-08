import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tests.conftest import INPUTS, analysis_fixture
from roleready.api import create_app
from roleready.engine import Engine, parse_json_response, validate_analysis
from roleready.schemas import Analysis, ServiceError, SessionInput
from roleready.settings import Settings
from roleready.storage import Actor, LocalStore


def test_unconfigured_generator_returns_error_without_fake_session(tmp_path):
    app = create_app(Settings(_env_file=None, state_dir=tmp_path, track_api_metrics=False, generation_url=""))
    with TestClient(app, headers={"Authorization": "Bearer local-development"}) as client:
        response = client.post("/v1/sessions", json=INPUTS)
        assert response.status_code == 503
        assert response.json()["code"] == "generator_not_configured"
        assert client.get("/v1/sessions").json() == []


def test_generated_evidence_and_seven_question_contract():
    inputs = SessionInput(**INPUTS)
    analysis = analysis_fixture()
    assert validate_analysis(analysis, inputs, set()).questions[-1].id == "q7"
    analysis.findings[0].cv_quote = "made up achievement"
    with pytest.raises(ServiceError, match="CV claim"):
        validate_analysis(analysis, inputs, set())
    item = analysis_fixture().model_dump()
    item["questions"][1]["text"] = item["questions"][0]["text"]
    with pytest.raises(ValidationError):
        Analysis.model_validate(item)
    item["questions"].pop()
    with pytest.raises(ValidationError):
        Analysis.model_validate(item)


def test_json_and_score_fail_closed(monkeypatch):
    assert parse_json_response('```json\n{"value": 1}\n```') == {"value": 1}
    with pytest.raises(ServiceError):
        parse_json_response("not JSON")
    engine = Engine(Settings(_env_file=None))

    async def invalid_chat(*_args, **_kwargs):
        return "Looks good, 99 percent."

    monkeypatch.setattr(engine, "chat", invalid_chat)
    with pytest.raises(ServiceError, match="valid rubric score"):
        asyncio.run(engine.score(analysis_fixture().questions[0].model_dump(), "A candidate answer."))

    async def valid_chat(*_args, **_kwargs):
        return "Feedback: Explain the validation approach with more detail. [RESULT] 3"

    monkeypatch.setattr(engine, "chat", valid_chat)
    assert (
        asyncio.run(engine.score(analysis_fixture().questions[0].model_dump(), "A candidate answer.")).score
        == 3
    )


def test_optimistic_updates_prevent_lost_answers(tmp_path):
    async def scenario():
        store = LocalStore(tmp_path / "state.db")
        actor = Actor("owner")
        item = {"id": "one", "version": 1, "answers": {}}
        await store.create(actor, item)
        first, stale = deepcopy(item), deepcopy(item)
        first["answers"]["q1"] = "first"
        await store.save(actor, first, 1)
        stale["answers"]["q2"] = "second"
        with pytest.raises(ServiceError, match="changed"):
            await store.save(actor, stale, 1)
        assert (await store.get(actor, "one"))["answers"] == {"q1": "first"}

    asyncio.run(scenario())


def test_production_requires_supabase():
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(_env_file=None, environment="production", auth_mode="local")


def test_remote_auth_uses_verified_user_endpoint(tmp_path, monkeypatch):
    real_client = httpx.AsyncClient
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(401, json={"message": "bad jwt"})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)
    )
    settings = Settings(
        _env_file=None,
        auth_mode="supabase",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-public-key",
        state_dir=tmp_path,
        track_api_metrics=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/sessions", headers={"Authorization": "Bearer untrusted-jwt"})
        assert response.status_code == 401
    assert str(seen[0].url) == "https://test.supabase.co/auth/v1/user"
    assert seen[0].headers["Authorization"] == "Bearer untrusted-jwt"
