"""Explicitly configured OpenAI-compatible endpoint adapter for Qwen.

The project does not provide model weights or external accounts. No candidate
resume is transmitted until the caller deliberately runs a configured endpoint.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"


class ModelUnavailable(RuntimeError):
    pass


class OpenAICompatibleQwen:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 120,
    ) -> None:
        self.base_url = (base_url or os.environ.get("ROLEREADY_QWEN_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("ROLEREADY_QWEN_MODEL", DEFAULT_MODEL)
        self.api_key = api_key if api_key is not None else os.environ.get("ROLEREADY_QWEN_API_KEY", "")
        self.timeout = timeout
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ModelUnavailable("Set ROLEREADY_QWEN_BASE_URL to an explicit OpenAI-compatible /v1 endpoint.")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ModelUnavailable("Non-local endpoints must use HTTPS to avoid exposing candidate CVs.")

    def complete_json(self, *, system: str, user: str) -> dict[str, object]:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 2200,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(
            self.base_url + "/chat/completions", data=body,
            headers=headers, method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                envelope = json.loads(response.read(2_000_000).decode("utf-8"))
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ModelUnavailable("Model returned a non-text response.")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("Model response must be a JSON object")
            return parsed
        except (HTTPError, URLError, KeyError, IndexError, UnicodeError, ValueError) as exc:
            raise ModelUnavailable(f"Qwen inference unavailable or response invalid: {type(exc).__name__}") from exc
