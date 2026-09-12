"""OpenRouter API embedder for remote embeddings via the OpenRouter API.

Calls OpenRouter's /embeddings endpoint with retry/backoff.
Batches up to OPENROUTER_EMBED_BATCH_SIZE texts per request for efficiency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np

from src import config


class EmbedError(RuntimeError):
    """Raised when the embedding API cannot produce vectors after retries."""


@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    model: str
    usage: dict[str, Any] | None = None


class OpenRouterEmbedder:
    """OpenAI-compatible embeddings caller via OpenRouter."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.base_url = (base_url or config.OPENROUTER_BASE_URL).rstrip("/")
        self.model = model or config.OPENROUTER_EMBEDDING_MODEL
        self.timeout = timeout if timeout is not None else config.OPENROUTER_EMBED_TIMEOUT_SEC
        self.max_retries = (
            max_retries if max_retries is not None else config.OPENROUTER_EMBED_MAX_RETRIES
        )
        self.batch_size = (
            batch_size
            if batch_size is not None
            else config.OPENROUTER_EMBED_BATCH_SIZE
        )
        if not self.api_key:
            raise EmbedError(
                "OPENROUTER_API_KEY is not set. Add it to .env (see .env.example)."
            )
        self._endpoint = f"{self.base_url}/embeddings"

    def encode(self, texts: list[str], **_: Any) -> Any:
        """Encode a list of texts into embeddings.

        Returns a numpy array of shape (len(texts), embedding_dim) to match
        the sentence-transformers interface.
        """
        if not texts:
            return np.array([])

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = self._embed_batch(batch)
            all_embeddings.extend(response.embeddings)

        return np.array(all_embeddings)

    def _embed_batch(self, texts: list[str]) -> EmbeddingResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://regulatory-compliance.local",
            "X-Title": "Regulatory Compliance RAG",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
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
                # Rate limit — wait and retry
                wait = retry_after or self._backoff_sec(attempt)
                if attempt < self.max_retries:
                    self._sleep(wait)
                    continue
                raise EmbedError(
                    f"OpenRouter rate limit reached after {self.max_retries} retries."
                )
            if 500 <= resp.status_code < 600:
                last_exc = EmbedError(
                    f"upstream {resp.status_code}: {self._safe_body(resp)[:200]}"
                )
                if attempt < self.max_retries:
                    self._sleep(retry_after or self._backoff_sec(attempt))
                    continue
                break
            # 4xx (non-429): don't retry
            raise EmbedError(
                f"OpenRouter request failed ({resp.status_code}): "
                f"{self._safe_body(resp)[:300]}"
            )

        raise EmbedError(
            f"OpenRouter request failed after {self.max_retries} retries: {last_exc}"
        )

    @staticmethod
    def _parse_ok(body: dict[str, Any]) -> EmbeddingResponse:
        try:
            embeddings = [item["embedding"] for item in body["data"]]
        except (KeyError, TypeError) as exc:
            raise EmbedError(f"unexpected OpenRouter response shape: {body}") from exc
        return EmbeddingResponse(
            embeddings=embeddings,
            model=body.get("model", ""),
            usage=body.get("usage"),
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
        return min(60.0, 2.0 * (2 ** attempt))

    def _sleep_backoff(self, attempt: int) -> None:
        self._sleep(self._backoff_sec(attempt))

    @staticmethod
    def _sleep(seconds: float) -> None:
        if seconds and seconds > 0:
            time.sleep(seconds)


def get_openrouter_embedder(**kw: Any) -> OpenRouterEmbedder:
    """Factory used by the embedding pipeline."""
    return OpenRouterEmbedder(**kw)
