import jwt
from fastapi import status
from backend.app.config import settings


def test_auth_access_isolation_between_candidates(client):
    # Candidate A creates session
    token_a = jwt.encode({"sub": "candidate_alice_123"}, "dummy_key", algorithm="HS256")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    create_res = client.post(
        "/sessions",
        data={
            "target_role": "Data Engineer",
            "job_text": "Building scalable Spark and Kafka data pipelines.",
            "cv_text": "Experienced Python data engineer.",
        },
        headers=headers_a,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_id = create_res.json()["session_id"]

    # Candidate A can access their own session
    get_res_a = client.get(f"/sessions/{session_id}", headers=headers_a)
    assert get_res_a.status_code == status.HTTP_200_OK

    # Candidate B tries to access Candidate A's session
    token_b = jwt.encode({"sub": "candidate_bob_999"}, "dummy_key", algorithm="HS256")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    get_res_b = client.get(f"/sessions/{session_id}", headers=headers_b)
    assert get_res_b.status_code == status.HTTP_403_FORBIDDEN


def test_auth_enforce_jwt_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENFORCE_JWT", True)

    # Missing header should yield 401
    res = client.get("/sessions/some_id")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
