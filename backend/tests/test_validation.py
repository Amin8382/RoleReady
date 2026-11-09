import io
from fastapi import status


def test_create_session_success(client):
    payload = {
        "target_role": "Machine Learning Engineer",
        "experience_level": "mid",
        "job_text": "We need a Machine Learning Engineer with strong PyTorch experience.",
        "cv_text": "3 years experience developing computer vision and NLP models in Python.",
    }
    response = client.post("/sessions", data=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "session_id" in data
    assert data["target_role"] == "Machine Learning Engineer"
    assert data["status"] == "created"


def test_create_session_empty_file_rejected(client):
    files = {"cv_file": ("resume.pdf", io.BytesIO(b""), "application/pdf")}
    data = {
        "target_role": "Data Scientist",
        "job_text": "Machine Learning position with Python requirements.",
    }
    response = client.post("/sessions", data=data, files=files)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "empty" in response.json()["detail"].lower()


def test_create_session_unsupported_file_extension_rejected(client):
    files = {"cv_file": ("resume.exe", io.BytesIO(b"Malicious binary content"), "application/octet-stream")}
    data = {
        "target_role": "Backend Engineer",
        "job_text": "Backend API engineer using Python FastAPI and databases.",
    }
    response = client.post("/sessions", data=data, files=files)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "unsupported" in response.json()["detail"].lower()


def test_create_session_oversized_file_rejected(client):
    # Over 5 MB
    large_bytes = b"0" * (6 * 1024 * 1024)
    files = {"cv_file": ("large_cv.txt", io.BytesIO(large_bytes), "text/plain")}
    data = {
        "target_role": "DevOps Engineer",
        "job_text": "DevOps engineer with Kubernetes and Docker knowledge.",
    }
    response = client.post("/sessions", data=data, files=files)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "exceeds" in response.json()["detail"].lower()


def test_create_session_missing_job_text_rejected(client):
    data = {
        "target_role": "Frontend Developer",
        "cv_text": "React and TypeScript engineer with 2 years experience.",
        "job_text": "",
    }
    response = client.post("/sessions", data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
