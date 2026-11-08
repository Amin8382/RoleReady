from io import BytesIO

from pypdf import PdfReader

from tests.conftest import INPUTS
from roleready.api import authenticate
from roleready.storage import Actor


def create(client):
    result = client.post("/v1/sessions", json=INPUTS)
    assert result.status_code == 201, result.text
    return result.json()


def test_complete_seven_answer_workflow_resume_pdf_delete(client):
    item = create(client)
    sid = item["id"]
    assert len(item["analysis"]["questions"]) == 7
    assert client.post(f"/v1/sessions/{sid}/report").status_code == 409
    for i in range(1, 8):
        response = client.post(
            f"/v1/sessions/{sid}/answers",
            json={
                "question_id": f"q{i}",
                "transcript": "I would validate the approach with a separate test dataset.",
            },
        )
        assert response.status_code == 200, response.text
    assert client.get(f"/v1/sessions/{sid}").json()["answers"]["q7"]["evaluation"]["score"] == 3
    result = client.post(f"/v1/sessions/{sid}/report").json()
    assert result["report"]["average_score"] == 3
    assert len(result["report"]["items"]) == 7
    pdf = client.get(f"/v1/sessions/{sid}/report.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "RoleReady" in text and "validation approach" in text
    assert client.get("/v1/sessions").json()[0]["answered"] == 7
    # Resubmission invalidates a stale report, even when the new score is identical.
    response = client.post(
        f"/v1/sessions/{sid}/answers",
        json={"question_id": "q1", "transcript": "I would also check contamination in the input features."},
    )
    assert response.json()["report"] is None
    assert client.get(f"/v1/sessions/{sid}/report.pdf").status_code == 409
    assert client.delete(f"/v1/sessions/{sid}").status_code == 204
    assert client.get(f"/v1/sessions/{sid}").status_code == 404


def test_transcript_correction_and_provider_failure_preserve_saved_work(client):
    item = create(client)
    sid = item["id"]
    response = client.post(
        f"/v1/sessions/{sid}/transcribe",
        data={"question_id": "q1"},
        files={"file": ("test.wav", b"synthetic-test")},
    )
    assert response.status_code == 200
    original = response.json()["transcript"]
    corrected = "I corrected a technical term and explained the approach."
    response = client.post(f"/v1/sessions/{sid}/answers", json={"question_id": "q1", "transcript": corrected})
    saved = response.json()["answers"]["q1"]
    assert saved["transcript"] == corrected
    assert saved["original_transcript"] == original
    client.app.state.engine.fail = True
    response = client.post(
        f"/v1/sessions/{sid}/answers",
        json={
            "question_id": "q1",
            "transcript": "A different answer should not replace saved work on failure.",
        },
    )
    assert response.status_code == 502
    assert client.get(f"/v1/sessions/{sid}").json()["answers"]["q1"] == saved


def test_cross_owner_reads_updates_and_deletes_are_denied(client):
    sid = create(client)["id"]
    client.app.dependency_overrides[authenticate] = lambda: Actor("another-user")
    assert client.get("/v1/sessions").json() == []
    assert client.get(f"/v1/sessions/{sid}").status_code == 404
    assert client.delete(f"/v1/sessions/{sid}").status_code == 404
    assert (
        client.post(
            f"/v1/sessions/{sid}/answers",
            json={"question_id": "q1", "transcript": "I cannot modify another person's answer."},
        ).status_code
        == 404
    )
    client.app.dependency_overrides.clear()
    assert client.get(f"/v1/sessions/{sid}").status_code == 200


def test_input_authentication_and_document_failures(client):
    assert client.get("/v1/sessions", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/v1/sessions", json={**INPUTS, "cv_text": "short"}).status_code == 422
    assert client.post("/v1/extract", files={"file": ("test.exe", b"not a document")}).status_code == 415
    assert client.post("/v1/extract", files={"file": ("test.pdf", b"not a PDF")}).status_code == 422
    response = client.post("/v1/extract", files={"file": ("test.txt", INPUTS["cv_text"].encode())})
    assert response.json()["text"] == INPUTS["cv_text"]
    item = create(client)
    assert (
        client.post(
            f"/v1/sessions/{item['id']}/answers",
            json={"question_id": "unknown", "transcript": "This question is not in this session."},
        ).status_code
        == 404
    )
