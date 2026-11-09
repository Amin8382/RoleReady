from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    DATABASE_BACKEND: str = "sqlite"
    SQLITE_DB_PATH: str = "backend/data/roleready_local.db"

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_STORAGE_BUCKET: str = "cv-uploads"

    AUTH_ENFORCE_JWT: bool = False

    SCORER_BACKEND: str = "mock"
    PROMETHEUS_ENDPOINT: str = "http://localhost:11434/api/generate"
    PROMETHEUS_MODEL_NAME: str = "prometheus-eval:7b-v2"
    PROMETHEUS_TIMEOUT_SECONDS: float = 45.0
    PROMETHEUS_API_KEY: str = ""

    WHISPER_ENDPOINT: str = "http://localhost:8001/transcribe"
    KOKORO_ENDPOINT: str = "http://localhost:8002/speak"

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
