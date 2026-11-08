from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PAYLOAD = {
    "target_role": "Machine Learning Engineer",
    "experience_level": "junior",
    "cv_text": "Built a Python model with pandas and automated analytics reporting.",
    "job_description": "We seek a Machine Learning Engineer skilled in Python, SQL, Docker, and pandas.",
}

def test_health():
    assert client.get("/health").json() == {"status": "ok", "mode": "keyword_baseline"}

def test_session_has_seven_distinct_questions_and_evidence():
    response = client.post("/api/v1/sessions", json=PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "keyword_baseline"
    assert data["experience_level"] == "junior"
    assert len(data["questions"]) == 7
    assert len({q["text"] for q in data["questions"]}) == 7
    assert all(q["source_ids"] == [] for q in data["questions"])
    assert "python" in [x["requirement"] for x in data["analysis"]["strengths"]]
    assert "docker" in [x["requirement"] for x in data["analysis"]["requirements_not_evidenced"]]
    assert "sql" in [x["requirement"] for x in data["analysis"]["requirements_not_evidenced"]]

def test_empty_and_invalid_inputs_rejected():
    assert client.post("/api/v1/sessions", json={}).status_code == 422
    assert client.post("/api/v1/sessions", json={**PAYLOAD, "experience_level": "expert"}).status_code == 422

def test_unconfigured_evaluator_fails_explicitly():
    response = client.post("/api/v1/evaluations", json={
        "session_id": "test", "question_id": "q1", "question_text": "What did you build?",
        "original_transcript": "I built it", "corrected_transcript": "I built it",
        "reference_criteria": ["Personal contribution"],
    })
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "MODEL_NOT_CONFIGURED"
