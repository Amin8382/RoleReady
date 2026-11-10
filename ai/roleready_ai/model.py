"""Explicitly configured OpenAI-compatible endpoint adapter for Qwen.

The project does not provide model weights or external accounts. No candidate
resume is transmitted until the caller deliberately runs a configured endpoint.
"""
from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"


class ModelUnavailable(RuntimeError):
    pass


class InvalidModelResponse(ModelUnavailable):
    """A successful HTTP call did not produce a complete, valid JSON result."""


def strict_json(text: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError("Nonstandard JSON constant")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


class OpenAICompatibleQwen:
    def configure_response_schema(self, schema: dict[str, object]) -> None:
        """Allow the question pipeline to constrain evidence/citations per input."""
        self.response_schema = schema

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 300,
        response_schema: dict[str, object] | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.base_url = (base_url or os.environ.get("ROLEREADY_QWEN_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("ROLEREADY_QWEN_MODEL", DEFAULT_MODEL)
        self.api_key = api_key if api_key is not None else os.environ.get("ROLEREADY_QWEN_API_KEY", "")
        if not 0 < timeout <= 600:
            raise ValueError("timeout must be positive and at most 600 seconds")
        self.timeout = timeout
        self.response_schema = response_schema
        self.reasoning_effort = (
            reasoning_effort if reasoning_effort is not None
            else os.environ.get("ROLEREADY_QWEN_REASONING_EFFORT", "")
        )
        if not 1 <= max_tokens <= 8192:
            raise ValueError("max_tokens must be 1-8192")
        self.max_tokens = max_tokens
        self.last_response: dict[str, object] = {}
        self.last_content: str | None = None
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ModelUnavailable("Set ROLEREADY_QWEN_BASE_URL to an explicit OpenAI-compatible /v1 endpoint.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ModelUnavailable("Endpoint URL must not contain credentials, query parameters or fragments.")
        if not self.model.strip():
            raise ModelUnavailable("A served model identifier is required")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ModelUnavailable("Non-local endpoints must use HTTPS to avoid exposing candidate CVs.")

    def complete_json(self, *, system: str, user: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        if self.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "interview_questions", "strict": True,
                                "schema": self.response_schema},
            }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(
            self.base_url + "/chat/completions", data=body,
            headers=headers, method="POST",
        )
        self.last_response = {}
        self.last_content = None
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Response exceeds size limit")
            envelope = strict_json(raw.decode("utf-8"))
            choice = envelope["choices"][0]
            self.last_response = {
                "model": envelope.get("model"), "finish_reason": choice.get("finish_reason"),
                "usage": envelope.get("usage"),
                "server_timings": envelope.get("timings"),
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "reasoning_characters": sum(
                    len(value) for field in ("reasoning", "reasoning_content", "thinking")
                    if isinstance(value := choice["message"].get(field), str)
                ),
            }
            content = choice["message"]["content"]
            self.last_content = content if isinstance(content, str) else None
            if envelope.get("model") != self.model:
                raise ValueError("Response model identity does not match requested model")
            if choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete model response (finish_reason is not stop)")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Model returned no final text content")
            parsed = strict_json(content)
            if not isinstance(parsed, dict):
                raise ValueError("Model response must be a JSON object")
            return parsed
        except (HTTPError, URLError, TimeoutError) as exc:
            status = f" (HTTP {exc.code})" if isinstance(exc, HTTPError) else ""
            self.last_response = {"error_type": type(exc).__name__, "http_status": getattr(exc, "code", None),
                                  "latency_ms": round((time.perf_counter() - started) * 1000)}
            raise ModelUnavailable(f"Qwen endpoint request failed: {type(exc).__name__}{status}") from exc
        except (KeyError, IndexError, TypeError, AttributeError, UnicodeError, ValueError) as exc:
            raise InvalidModelResponse(
                f"Qwen response rejected: {type(exc).__name__}; check model identity, finish reason and strict JSON"
            ) from exc
