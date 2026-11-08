"""Owner-scoped persistence, with optimistic updates to avoid lost answers."""

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from roleready.schemas import ServiceError


@dataclass(frozen=True)
class Actor:
    id: str
    token: str = ""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def summary(item: dict) -> dict:
    return {
        "id": item["id"],
        "role": item["inputs"]["role"],
        "created_at": item["created_at"],
        "answered": len(item["answers"]),
        "has_report": item.get("report") is not None,
        "mode": item["mode"],
    }


class LocalStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS owner_updated ON sessions(owner, updated_at)")

    async def create(self, actor: Actor, item: dict):
        def operation():
            with sqlite3.connect(self.path) as db:
                db.execute(
                    "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                    (item["id"], actor.id, json.dumps(item), item["version"], now()),
                )

        await asyncio.to_thread(operation)

    async def get(self, actor: Actor, sid: str) -> dict:
        def operation():
            with sqlite3.connect(self.path) as db:
                row = db.execute(
                    "SELECT payload FROM sessions WHERE id=? AND owner=?", (sid, actor.id)
                ).fetchone()
            if row is None:
                raise ServiceError("not_found", "Session not found.", 404)
            return json.loads(row[0])

        return await asyncio.to_thread(operation)

    async def list(self, actor: Actor):
        def operation():
            with sqlite3.connect(self.path) as db:
                rows = db.execute(
                    "SELECT payload FROM sessions WHERE owner=? ORDER BY updated_at DESC LIMIT 100",
                    (actor.id,),
                ).fetchall()
            return [summary(json.loads(row[0])) for row in rows]

        return await asyncio.to_thread(operation)

    async def save(self, actor: Actor, item: dict, expected_version: int):
        item["version"] = expected_version + 1

        def operation():
            with sqlite3.connect(self.path) as db:
                result = db.execute(
                    "UPDATE sessions SET payload=?, version=?, updated_at=? WHERE id=? AND owner=? AND version=?",
                    (json.dumps(item), item["version"], now(), item["id"], actor.id, expected_version),
                )
                if result.rowcount != 1:
                    raise ServiceError(
                        "session_changed",
                        "This session changed in another request. Reopen it before retrying.",
                        409,
                    )

        await asyncio.to_thread(operation)

    async def delete(self, actor: Actor, sid: str):
        def operation():
            with sqlite3.connect(self.path) as db:
                result = db.execute("DELETE FROM sessions WHERE id=? AND owner=?", (sid, actor.id))
                if result.rowcount != 1:
                    raise ServiceError("not_found", "Session not found.", 404)

        await asyncio.to_thread(operation)


class SupabaseStore:
    def __init__(self, url: str, key: str):
        self.url, self.key = url.rstrip("/"), key

    async def request(self, actor, method, params=None, body=None):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    self.url + "/rest/v1/roleready_sessions",
                    params=params,
                    json=body,
                    headers={
                        "apikey": self.key,
                        "Authorization": f"Bearer {actor.token}",
                        "Prefer": "return=representation",
                    },
                )
            if response.status_code in (401, 403):
                raise ServiceError("unauthorized", "Please sign in again.", 401)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                "storage_unavailable", "Session storage is unavailable. Please retry."
            ) from exc

    async def create(self, actor, item):
        await self.request(
            actor,
            "POST",
            body={"id": item["id"], "user_id": actor.id, "payload": item, "version": item["version"]},
        )

    async def get(self, actor, sid):
        rows = await self.request(
            actor, "GET", {"id": f"eq.{sid}", "user_id": f"eq.{actor.id}", "select": "payload"}
        )
        if not rows:
            raise ServiceError("not_found", "Session not found.", 404)
        return rows[0]["payload"]

    async def list(self, actor):
        rows = await self.request(
            actor,
            "GET",
            {"user_id": f"eq.{actor.id}", "select": "payload", "order": "updated_at.desc", "limit": "100"},
        )
        return [summary(row["payload"]) for row in rows]

    async def save(self, actor, item, expected_version):
        item["version"] = expected_version + 1
        rows = await self.request(
            actor,
            "PATCH",
            {"id": f"eq.{item['id']}", "user_id": f"eq.{actor.id}", "version": f"eq.{expected_version}"},
            {"payload": item, "version": item["version"], "updated_at": now()},
        )
        if not rows:
            raise ServiceError(
                "session_changed", "This session changed in another request. Reopen it before retrying.", 409
            )

    async def delete(self, actor, sid):
        rows = await self.request(actor, "DELETE", {"id": f"eq.{sid}", "user_id": f"eq.{actor.id}"})
        if not rows:
            raise ServiceError("not_found", "Session not found.", 404)
