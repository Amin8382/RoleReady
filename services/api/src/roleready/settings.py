from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from roleready.paths import ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROLEREADY_", env_file=ROOT / ".env", extra="ignore")
    environment: Literal["development", "production"] = "development"
    auth_mode: Literal["local", "supabase"] = "local"
    local_token: str = "local-development"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    question_mode: Literal["llm", "retrieval"] = "llm"
    retriever: Literal["bge", "tfidf"] = "bge"
    generation_url: str = ""
    generation_key: str = ""
    generation_model: str = "Qwen/Qwen3.5-4B"
    evaluation_url: str = ""
    evaluation_key: str = ""
    evaluation_model: str = "prometheus-eval/prometheus-7b-v2.0"
    model_timeout_seconds: float = 180
    voice_enabled: bool = False
    data_root: Path = ROOT
    state_dir: Path = ROOT / ".state"
    track_api_metrics: bool = True

    @model_validator(mode="after")
    def validate_modes(self):
        if self.environment == "production" and self.auth_mode != "supabase":
            raise ValueError("Production requires Supabase authentication")
        if self.auth_mode == "supabase" and not (
            self.supabase_url.startswith("https://") and self.supabase_anon_key
        ):
            raise ValueError("Supabase URL and publishable/anon key are required")
        for url in [self.generation_url, self.evaluation_url]:
            if url and not url.startswith(("http://", "https://")):
                raise ValueError("Model base URLs must use HTTP or HTTPS")
        return self
