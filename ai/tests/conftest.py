"""Small, authored source fixtures. No external data or network calls."""
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def source_fixture(tmp_path):
    sources = []
    raw = tmp_path / "raw"
    registry = tmp_path / "sources.json"

    def row(question="How would you validate a SQL join with duplicate customer keys?", role="Data Analyst", **updates):
        return {"question": question, "role": role, "keywords": "['SQL', 'joins']",
                "question_category": "Coding & Problem Solving", "question_level": "Level 1: Foundational",
                "sector": "synthetic-test", "interview_stage": "test", "interviewer": "synthetic", **updates}

    def add(rows, *, source_id=None, usage="retrieval_corpus", license_verified=True, data_bytes=None):
        source_id = source_id or "fixture-" + str(len(sources))
        revision = "a" * 40
        data = data_bytes if data_bytes is not None else "".join(json.dumps(r) + "\n" for r in rows).encode()
        path = raw / source_id / revision / "questions.jsonl"
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
        source = {"source_id": source_id, "revision": revision, "repo_id": "tests/" + source_id,
                  "url": "https://example.invalid/fixture", "publisher": "synthetic-test",
                  "usage": usage, "license": "mit", "license_verified": license_verified,
                  "authorship": "synthetic-test", "upstream_split": "train",
                  "first_verified_download_utc": "2026-01-01T00:00:00+00:00",
                  "files": [{"path": "questions.jsonl", "bytes": len(data), "sha256": sha256(data).hexdigest()}]}
        sources.append(source)
        registry.write_text(json.dumps({"schema_version": "source-registry-1.0", "sources": sources}), encoding="utf-8")
        return source
    return SimpleNamespace(row=row, add=add, raw=raw, registry=registry, sources=sources, tmp=tmp_path)
