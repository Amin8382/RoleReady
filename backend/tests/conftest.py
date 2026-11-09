import os
import pytest
from fastapi.testclient import TestClient

# Ensure test DB
os.environ["DATABASE_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = "backend/data/roleready_test.db"
os.environ["AUTH_ENFORCE_JWT"] = "false"
os.environ["SCORER_BACKEND"] = "mock"

from backend.app.main import app
from backend.app.database import get_repository


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    # Close connections before removing file
    test_db = "backend/data/roleready_test.db"
    try:
        if os.path.exists(test_db):
            os.remove(test_db)
    except PermissionError:
        pass


@pytest.fixture(autouse=True)
def clean_db():
    repo = get_repository()
    yield
