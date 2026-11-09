import json
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from .base import BaseRepository


class SQLiteRepository(BaseRepository):
    """
    Self-contained SQLite storage engine.
    Ensures the demo runs immediately on any developer machine without Supabase credentials.
    """

    def __init__(self, db_path: str = "backend/data/roleready_local.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    target_role TEXT NOT NULL,
                    experience_level TEXT NOT NULL,
                    cv_text TEXT,
                    job_text TEXT NOT NULL,
                    cv_storage_path TEXT,
                    strengths TEXT DEFAULT '[]',
                    requirements_not_evidenced TEXT DEFAULT '[]',
                    supporting_source_excerpts TEXT DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'created',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    question_order INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    target_skill TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    reason_for_asking TEXT NOT NULL,
                    reference_criteria TEXT NOT NULL,
                    source_ids TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS answers (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    original_transcript TEXT NOT NULL,
                    corrected_transcript TEXT NOT NULL,
                    rubric_version TEXT NOT NULL,
                    correctness INTEGER NOT NULL,
                    coverage INTEGER NOT NULL,
                    relevance INTEGER NOT NULL,
                    evidence_and_structure INTEGER NOT NULL,
                    overall_score REAL NOT NULL,
                    evidence TEXT DEFAULT '[]',
                    feedback TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    average_score REAL NOT NULL,
                    priority_improvements TEXT NOT NULL,
                    cheat_sheet_content TEXT NOT NULL,
                    pdf_storage_path TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, user_id, target_role, experience_level, cv_text, job_text,
                    cv_storage_path, strengths, requirements_not_evidenced,
                    supporting_source_excerpts, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_data["id"],
                    session_data["user_id"],
                    session_data["target_role"],
                    session_data["experience_level"],
                    session_data.get("cv_text"),
                    session_data["job_text"],
                    session_data.get("cv_storage_path"),
                    json.dumps(session_data.get("strengths", [])),
                    json.dumps(session_data.get("requirements_not_evidenced", [])),
                    json.dumps(session_data.get("supporting_source_excerpts", [])),
                    session_data.get("status", "created"),
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_session(session_data["id"])

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["strengths"] = json.loads(data["strengths"])
            data["requirements_not_evidenced"] = json.loads(data["requirements_not_evidenced"])
            data["supporting_source_excerpts"] = json.loads(data["supporting_source_excerpts"])
            return data

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        set_clauses = []
        values = []
        for k, v in updates.items():
            if k in ["strengths", "requirements_not_evidenced", "supporting_source_excerpts"]:
                set_clauses.append(f"{k} = ?")
                values.append(json.dumps(v))
            else:
                set_clauses.append(f"{k} = ?")
                values.append(v)
        set_clauses.append("updated_at = ?")
        values.append(now)
        values.append(session_id)

        query = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, values)
            conn.commit()
        return self.get_session(session_id)

    def list_sessions_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["strengths"] = json.loads(item["strengths"])
                item["requirements_not_evidenced"] = json.loads(item["requirements_not_evidenced"])
                item["supporting_source_excerpts"] = json.loads(item["supporting_source_excerpts"])
                results.append(item)
            return results

    def save_questions(self, session_id: str, user_id: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # Delete old questions for session if any
            conn.execute("DELETE FROM questions WHERE session_id = ?", (session_id,))
            for idx, q in enumerate(questions, start=1):
                conn.execute(
                    """
                    INSERT INTO questions (
                        id, session_id, user_id, question_order, text, target_skill,
                        difficulty, reason_for_asking, reference_criteria, source_ids, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        q["question_id"],
                        session_id,
                        user_id,
                        idx,
                        q["text"],
                        q["target_skill"],
                        q.get("difficulty", "medium"),
                        q["reason_for_asking"],
                        q["reference_criteria"],
                        json.dumps(q.get("source_ids", [])),
                        now,
                    ),
                )
            conn.commit()
        return self.get_questions(session_id)

    def get_questions(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM questions WHERE session_id = ? ORDER BY question_order ASC", (session_id,))
            rows = cursor.fetchall()
            out = []
            for r in rows:
                item = dict(r)
                item["question_id"] = item["id"]
                item["source_ids"] = json.loads(item["source_ids"])
                out.append(item)
            return out

    def save_answer(self, answer_data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # Upsert answer for question in this session
            conn.execute(
                """
                DELETE FROM answers WHERE session_id = ? AND question_id = ?
                """,
                (answer_data["session_id"], answer_data["question_id"]),
            )
            conn.execute(
                """
                INSERT INTO answers (
                    id, session_id, question_id, user_id, original_transcript,
                    corrected_transcript, rubric_version, correctness, coverage,
                    relevance, evidence_and_structure, overall_score, evidence,
                    feedback, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer_data["id"],
                    answer_data["session_id"],
                    answer_data["question_id"],
                    answer_data["user_id"],
                    answer_data["original_transcript"],
                    answer_data["corrected_transcript"],
                    answer_data.get("rubric_version", "v1.0"),
                    answer_data["scores"]["correctness"],
                    answer_data["scores"]["coverage"],
                    answer_data["scores"]["relevance"],
                    answer_data["scores"]["evidence_and_structure"],
                    answer_data["scores"]["overall_score"],
                    json.dumps(answer_data.get("evidence", [])),
                    answer_data["feedback"],
                    now,
                ),
            )
            conn.commit()
        return answer_data

    def get_answers(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM answers WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            rows = cursor.fetchall()
            out = []
            for r in rows:
                item = dict(r)
                item["evidence"] = json.loads(item["evidence"])
                item["scores"] = {
                    "correctness": item["correctness"],
                    "coverage": item["coverage"],
                    "relevance": item["relevance"],
                    "evidence_and_structure": item["evidence_and_structure"],
                    "overall_score": item["overall_score"],
                }
                out.append(item)
            return out

    def save_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM reports WHERE session_id = ?", (report_data["session_id"],))
            conn.execute(
                """
                INSERT INTO reports (
                    id, session_id, user_id, average_score, priority_improvements,
                    cheat_sheet_content, pdf_storage_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_data["id"],
                    report_data["session_id"],
                    report_data["user_id"],
                    report_data["average_score"],
                    json.dumps(report_data["priority_improvements"]),
                    json.dumps(report_data["cheat_sheet_content"]),
                    report_data.get("pdf_storage_path"),
                    now,
                ),
            )
            conn.commit()
        return report_data

    def get_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reports WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            item["priority_improvements"] = json.loads(item["priority_improvements"])
            item["cheat_sheet_content"] = json.loads(item["cheat_sheet_content"])
            return item

    def delete_user_data(self, user_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sessions WHERE user_id = ?", (user_id,))
            session_ids = [row["id"] for row in cursor.fetchall()]
            count = len(session_ids)
            for sid in session_ids:
                conn.execute("DELETE FROM answers WHERE session_id = ?", (sid,))
                conn.execute("DELETE FROM questions WHERE session_id = ?", (sid,))
                conn.execute("DELETE FROM reports WHERE session_id = ?", (sid,))
                conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            conn.commit()
            return count
