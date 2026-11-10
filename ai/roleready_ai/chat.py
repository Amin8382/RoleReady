"""Shared OpenAI-compatible text endpoint client for specialized model adapters."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class EndpointError(RuntimeError):
    pass


class ChatEndpoint:
    def __init__(
        self, *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise EndpointError("Set a valid OpenAI-compatible http(s) /v1 endpoint.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise EndpointError("Endpoint URL must not contain credentials or query parameters.")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise EndpointError("Remote endpoints require HTTPS to protect candidate answers.")
        if not model.strip():
            raise EndpointError("A served model identifier is required.")

    def complete(self, *, system: str, user: str, max_tokens: int = 1200) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(
            self.base_url + "/chat/completions",
            data=body, headers=headers, method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read(2_000_000).decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty or malformed model response")
            return content
        except (HTTPError, URLError, KeyError, IndexError, ValueError, UnicodeError) as exc:
            raise EndpointError(f"Chat model request failed: {type(exc).__name__}") from exc
