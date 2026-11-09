import os
import json
from typing import Optional, List, Dict, Any
import httpx
from .base import BaseRepository


class SupabaseRepository(BaseRepository):
    """
    Supabase repository using PostgREST HTTP API directly with service role or anon key.
    Enforces Row-Level Security and remote persistence.
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        self.url = supabase_url.rstrip("/")
        self.key = supabase_key
        self.rest_url = f"{self.url}/rest/v1"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=10.0, headers=self.headers)

    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._client() as client:
            res = client.post(f"{self.rest_url}/sessions", json=session_data)
            res.raise_for_status()
            rows = res.json()
            return rows[0] if rows else session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._client() as client:
            res = client.get(f"{self.rest_url}/sessions?id=eq.{session_id}&select=*")
            if res.status_code == 200:
                rows = res.json()
                return rows[0] if rows else None
            return None

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._client() as client:
            res = client.patch(f"{self.rest_url}/sessions?id=eq.{session_id}", json=updates)
            res.raise_for_status()
            rows = res.json()
            return rows[0] if rows else None

    def list_sessions_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        with self._client() as client:
            res = client.get(f"{self.rest_url}/sessions?user_id=eq.{user_id}&order=created_at.desc")
            if res.status_code == 200:
                return res.json()
            return []

    def save_questions(self, session_id: str, user_id: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        with self._client() as client:
            # Delete previous
            client.delete(f"{self.rest_url}/questions?session_id=eq.{session_id}")
            records = []
            for idx, q in enumerate(questions, start=1):
                records.append({
                    "id": q["question_id"],
                    "session_id": session_id,
                    "user_id": user_id,
                    "question_order": idx,
                    "text": q["text"],
                    "target_skill": q["target_skill"],
                    "difficulty": q.get("difficulty", "medium"),
                    "reason_for_asking": q["reason_for_asking"],
                    "reference_criteria": q["reference_criteria"],
                    "source_ids": q.get("source_ids", []),
                })
            res = client.post(f"{self.rest_url}/questions", json=records)
            res.raise_for_status()
            return self.get_questions(session_id)

    def get_questions(self, session_id: str) -> List[Dict[str, Any]]:
        with self._client() as client:
            res = client.get(f"{self.rest_url}/questions?session_id=eq.{session_id}&order=question_order.asc")
            if res.status_code == 200:
                rows = res.json()
                for r in rows:
                    r["question_id"] = r["id"]
                return rows
            return []

    def save_answer(self, answer_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._client() as client:
            payload = {
                "id": answer_data["id"],
                "session_id": answer_data["session_id"],
                "question_id": answer_data["question_id"],
                "user_id": answer_data["user_id"],
                "original_transcript": answer_data["original_transcript"],
                "corrected_transcript": answer_data["corrected_transcript"],
                "rubric_version": answer_data.get("rubric_version", "v1.0"),
                "correctness": answer_data["scores"]["correctness"],
                "coverage": answer_data["scores"]["coverage"],
                "relevance": answer_data["scores"]["relevance"],
                "evidence_and_structure": answer_data["scores"]["evidence_and_structure"],
                "overall_score": answer_data["scores"]["overall_score"],
                "evidence": answer_data.get("evidence", []),
                "feedback": answer_data["feedback"],
            }
            res = client.post(f"{self.rest_url}/answers", json=payload, headers={"Prefer": "resolution=merge-duplicates"})
            res.raise_for_status()
            return answer_data

    def get_answers(self, session_id: str) -> List[Dict[str, Any]]:
        with self._client() as client:
            res = client.get(f"{self.rest_url}/answers?session_id=eq.{session_id}&order=created_at.asc")
            if res.status_code == 200:
                rows = res.json()
                for item in rows:
                    item["scores"] = {
                        "correctness": item["correctness"],
                        "coverage": item["coverage"],
                        "relevance": item["relevance"],
                        "evidence_and_structure": item["evidence_and_structure"],
                        "overall_score": item["overall_score"],
                    }
                return rows
            return []

    def save_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._client() as client:
            payload = {
                "id": report_data["id"],
                "session_id": report_data["session_id"],
                "user_id": report_data["user_id"],
                "average_score": report_data["average_score"],
                "priority_improvements": report_data["priority_improvements"],
                "cheat_sheet_content": report_data["cheat_sheet_content"],
                "pdf_storage_path": report_data.get("pdf_storage_path"),
            }
            res = client.post(f"{self.rest_url}/reports", json=payload, headers={"Prefer": "resolution=merge-duplicates"})
            res.raise_for_status()
            return report_data

    def get_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._client() as client:
            res = client.get(f"{self.rest_url}/reports?session_id=eq.{session_id}&select=*")
            if res.status_code == 200:
                rows = res.json()
                return rows[0] if rows else None
            return None

    def delete_user_data(self, user_id: str) -> int:
        with self._client() as client:
            res = client.delete(f"{self.rest_url}/sessions?user_id=eq.{user_id}")
            return 1 if res.status_code in [200, 204] else 0
