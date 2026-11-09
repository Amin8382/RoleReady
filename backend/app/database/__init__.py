import os
from .base import BaseRepository
from .local_store import SQLiteRepository
from .supabase_client import SupabaseRepository

_repo_instance: BaseRepository = None


def get_repository() -> BaseRepository:
    """Factory function returning the configured repository."""
    global _repo_instance
    if _repo_instance is not None:
        return _repo_instance

    backend_type = os.getenv("DATABASE_BACKEND", "sqlite").lower()
    if backend_type == "supabase":
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
        if supabase_url and supabase_key:
            _repo_instance = SupabaseRepository(supabase_url, supabase_key)
            return _repo_instance

    # Default fallback: SQLite
    db_path = os.getenv("SQLITE_DB_PATH", "backend/data/roleready_local.db")
    _repo_instance = SQLiteRepository(db_path)
    return _repo_instance
