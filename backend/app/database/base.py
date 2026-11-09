from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BaseRepository(ABC):
    """Abstract interface for database operations (SQLite / Supabase)."""

    @abstractmethod
    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_sessions_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_questions(self, session_id: str, user_id: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_questions(self, session_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_answer(self, answer_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_answers(self, session_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_user_data(self, user_id: str) -> int:
        """Deletes all sessions, questions, answers, and reports for this user."""
        pass
