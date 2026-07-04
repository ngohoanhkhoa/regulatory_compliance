"""OpenCode Go API client for the generation step (§5.2).

OpenCode Go exposes an **OpenAI-compatible** chat-completions endpoint:
``POST {base}/chat/completions`` with ``Authorization: Bearer <key>`` and a
body ``{model, messages, temperature, max_tokens, stream}``. We use a plain
``httpx`` transport (no SDK lock-in) so the same client works for any
OpenAI-compatible provider, and a local Ollama/llama.cpp backend can be swapped
in by changing the base URL + removing the key (§1.1).

Defensive behaviour required by the spec (§5.2):
- Retry with exponential backoff on transient errors (429, 5xx, network).
- Surface the **5-hour rolling rate limit** with a clear, user-facing error
  message ("rate limit reached, try again in X minutes") rather than failing
  silently. We do *not* attempt to parse the exact retry-after for the rolling
  window (the API may not expose it); we use ``Retry-After`` when present and
  otherwise an exponentially growing wait.
- Never log the API key.

The client is behind the ``LLMClient`` Protocol so tests inject a fake and the
generation layer never imports the transport directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from src import config


class LLMError(RuntimeError):
    """Raised when the LLM API cannot produce an answer after retries."""


class RateLimitError(LLMError):
    """Specialised error for the 5-hour rolling limit (§5.2). Surfaces a
    user-facing message with a suggested wait time."""

    def __init__(self, message: str, retry_after_sec: float | None) -> None:
        mins = (
            f"{retry_after_sec / 60:.0f} minutes"
            if retry_after_sec is not None
            else "a few minutes"
        )
        super().__init__(f"{message} (try again in {mins})")
        self.retry_after_sec = retry_after_sec


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]], **kw: Any) -> LLMResponse: ...


class OpenCodeGoClient:
    """Thin OpenAI-compatible chat-completions caller with retry/backoff."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.api_key = api_key or config.OPENCODE_GO_API_KEY
        self.base_url = (base_url or config.OPENCODE_GO_BASE_URL).rstrip("/")
        self.model = model or config.OPENCODE_GO_MODEL
        self.timeout = timeout if timeout is not None else config.OPENCODE_GO_TIMEOUT_SEC
        self.max_retries = (
            max_retries if max_retries is not None else config.OPENCODE_GO_MAX_RETRIES
        )
        if not self.api_key:
            raise LLMError(
                "OPENCODE_GO_API_KEY is not set. Add it to .env (see .env.example)."
            )
        self._endpoint = f"{self.base_url}/chat/completions"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        **_: Any,
    ) -> LLMResponse:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": (
                config.OPENCODE_GO_TEMPERATURE if temperature is None else temperature
            ),
            "max_tokens": (
                config.OPENCODE_GO_MAX_TOKENS if max_tokens is None else max_tokens
            ),
            "stream": bool(stream),
        }

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = httpx.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if resp.status_code == 200:
                return self._parse_ok(resp.json())

            retry_after = self._retry_after_sec(resp)
            if resp.status_code == 429:
                # Hit the rolling 5h rate limit. Re-raise immediately per §5.2
                # (retrying within the same window will keep failing).
                raise RateLimitError(
                    "OpenCode Go rate limit reached.",
                    retry_after_sec=retry_after,
                )
            if 500 <= resp.status_code < 600:
                last_exc = LLMError(
                    f"upstream {resp.status_code}: {self._safe_body(resp)[:200]}"
                )
                if attempt < self.max_retries:
                    self._sleep(retry_after or self._backoff_sec(attempt))
                    continue
                break  # exhausted -> fall through to the after-loop raise
            # 4xx (non-429): don't retry — auth, bad request, etc.
            raise LLMError(
                f"OpenCode Go request failed ({resp.status_code}): "
                f"{self._safe_body(resp)[:300]}"
            )

        raise LLMError(f"OpenCode Go request failed after {self.max_retries} retries: {last_exc}")

    @staticmethod
    def _parse_ok(body: dict[str, Any]) -> LLMResponse:
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected OpenCode Go response shape: {body}") from exc
        return LLMResponse(
            text=text,
            model=body.get("model", ""),
            usage=body.get("usage"),
            raw=body,
        )

    @staticmethod
    def _retry_after_sec(resp: Any) -> float | None:
        val = getattr(resp, "headers", {}).get("retry-after") if hasattr(resp, "headers") else None
        if not val:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_body(resp: Any) -> str:
        try:
            return resp.text if hasattr(resp, "text") else str(resp.content)
        except Exception:
            return ""

    @staticmethod
    def _backoff_sec(attempt: int) -> float:
        return min(30.0, 1.0 * (2 ** attempt))

    def _sleep_backoff(self, attempt: int) -> None:
        self._sleep(self._backoff_sec(attempt))

    @staticmethod
    def _sleep(seconds: float) -> None:
        if seconds and seconds > 0:
            time.sleep(seconds)


def get_llm_client() -> LLMClient:
    """Default factory used by the generation pipeline (overridable in tests)."""
    return OpenCodeGoClient()


def is_configured() -> bool:
    """Cheap check for the API-detection step: is a key present at all?"""
    return bool(config.OPENCODE_GO_API_KEY)
