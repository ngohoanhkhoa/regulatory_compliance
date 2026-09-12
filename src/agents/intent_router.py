"""Intent router — classifies user messages and dispatches to expert agents."""

from __future__ import annotations

import time
from typing import Literal

import httpx

from src import config

Intent = Literal["question", "explore", "greeting"]

ROUTER_PROMPT = """\
Classify the user's message into exactly one category. Return ONLY the category name, nothing else.

Categories:
- greeting: The user is saying hello, thanks, goodbye, or making casual small talk. \
Any message that is purely social/conversational without asking for information.

- question: The user is asking about EU regulatory obligations, compliance requirements, \
legal provisions, or whether a specific law applies. Essentially any question that requires \
retrieving and interpreting legal text.

- explore: The user is asking about the dataset itself — statistics, counts, lists, \
browsing what acts exist, filtering by metadata (status, subject matter, authors, year, \
type), exploring the structure or contents of the CEPS EurLex corpus.

Message: {message}

Category:"""


class IntentRouter:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.base_url = (base_url or config.OPENROUTER_BASE_URL).rstrip("/")
        self.model = model or config.RERANKER_LLM_MODEL
        self._endpoint = f"{self.base_url}/chat/completions"

    def classify(self, message: str) -> Intent:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        prompt = ROUTER_PROMPT.format(message=message.strip()[:2000])
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 16,
        }

        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = httpx.post(self._endpoint, headers=headers, json=payload, timeout=15.0)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(1)
                continue

            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip().lower()
                if "explore" in content:
                    return "explore"
                if "greeting" in content:
                    return "greeting"
                return "question"

            last_exc = RuntimeError(f"router failed ({resp.status_code}): {resp.text[:200]}")
            if resp.status_code == 429:
                time.sleep(2)
                continue
            raise last_exc

        return "question"


_router: IntentRouter | None = None


def classify_intent(message: str) -> Intent:
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router.classify(message)
