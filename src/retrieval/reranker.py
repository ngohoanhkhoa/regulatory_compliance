"""LLM-based reranker for the merged hybrid candidate set (§5.2, §5.4).

The reranker sends the question + all candidates to a lightweight LLM via
OpenRouter and asks it to return relevance scores (0.0–1.0) in JSON. This
replaces the local cross-encoder model, removing the `sentence-transformers`
dependency entirely.

The reranker is behind a `Reranker` Protocol so tests/eval can inject a fake.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from src import config

RERANK_PROMPT = """\
You are a relevance scorer for a legal document retrieval system. \
Given a user question and a list of document chunks, rate how relevant \
each chunk is to the question on a scale from 0.0 (completely irrelevant) \
to 1.0 (perfectly relevant).

Consider:
- Does the chunk directly address the question?
- Does it contain specific regulatory obligations or legal provisions?
- Would this chunk help answer the question accurately?

Question: {question}

Chunks:
{chunks}

Return ONLY a JSON array of scores (floats between 0.0 and 1.0), \
one per chunk, in the same order. Example: [0.95, 0.32, 0.78, 0.15]"""


class Reranker(Protocol):
    def score(self, question: str, candidates: list[str]) -> list[float]: ...


class _LLMReranker:
    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or config.RERANKER_LLM_MODEL
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.base_url = (base_url or config.OPENROUTER_BASE_URL).rstrip("/")

        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Add it to .env (see .env.example)."
            )
        self._endpoint = f"{self.base_url}/chat/completions"

    def score(self, question: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []

        chunks_str = "\n".join(
            f"[{i}] {c[:500]}" for i, c in enumerate(candidates)
        )
        prompt = RERANK_PROMPT.format(question=question, chunks=chunks_str)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 256,
        }

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = httpx.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(min(10.0, 1.0 * (2 ** attempt)))
                continue

            if resp.status_code == 200:
                return self._parse_scores(resp.json(), len(candidates))

            if resp.status_code == 429:
                time.sleep(min(30.0, 2.0 * (2 ** attempt)))
                continue

            last_exc = RuntimeError(
                f"reranker LLM request failed ({resp.status_code}): "
                f"{resp.text[:200]}"
            )
            if 500 <= resp.status_code < 600 and attempt < 2:
                time.sleep(min(10.0, 1.0 * (2 ** attempt)))
                continue
            raise last_exc

        raise RuntimeError(
            f"reranker LLM request failed after retries: {last_exc}"
        )

    @staticmethod
    def _parse_scores(body: dict[str, Any], expected_count: int) -> list[float]:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected reranker response shape: {body}") from exc

        match = re.search(r"\[[\d.,\s]+\]", content)
        if not match:
            raise RuntimeError(
                f"reranker did not return a JSON array: {content[:200]}"
            )

        try:
            scores = json.loads(match.group())
        except json.JSONDecodeError:
            raise RuntimeError(
                f"reranker returned invalid JSON: {content[:200]}"
            )

        if not isinstance(scores, list) or not all(isinstance(s, (int, float)) for s in scores):
            raise RuntimeError(f"reranker returned non-numeric scores: {content[:200]}")

        scores = [float(s) for s in scores]

        if len(scores) != expected_count:
            scores = (scores[:expected_count] if len(scores) > expected_count
                      else scores + [0.0] * (expected_count - len(scores)))

        return scores


def get_reranker() -> Reranker:
    return _LLMReranker()


@dataclass
class RerankedHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any]
    rerank_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
            "rerank_score": self.rerank_score,
        }


def rerank(
    question: str,
    hits: list[dict[str, Any]],
    *,
    reranker: Reranker | None = None,
    top_k: int = config.DEFAULT_TOP_K,
) -> list[RerankedHit]:
    """Re-score a candidate list and return the top-k by reranker score.

    `hits` is the fused candidate list (any remaining hybrid scores are kept
    on the output for auditing but are not used for ordering).
    """
    if not hits:
        return []
    reranker = reranker or get_reranker()
    texts = [h.get("text") or "" for h in hits]
    scores = reranker.score(question, texts)
    ranked = sorted(
        zip(hits, scores), key=lambda hs: hs[1], reverse=True
    )
    out: list[RerankedHit] = []
    for h, rs in ranked[:top_k]:
        out.append(
            RerankedHit(
                chunk_id=str(h.get("chunk_id")),
                score=float(h.get("score") or 0.0),
                text=str(h.get("text") or ""),
                metadata=dict(h.get("metadata") or {}),
                rerank_score=float(rs),
            )
        )
    return out
