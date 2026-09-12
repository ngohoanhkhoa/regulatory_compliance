"""Greeting Agent — handles casual/greeting messages directly without retrieval."""

from __future__ import annotations

import time
from typing import Any

import httpx

from src import config

GREETING_PROMPT = """\
You are a friendly assistant for an EU regulatory compliance chatbot. The user \
sent a casual message (greeting, small talk, "thanks", etc.). Respond warmly and \
concisely. Mention that you can help with EU legal questions and dataset exploration.

Examples of what you can do:
- Answer legal questions about EU regulations (e.g. "Is the GDPR still in force?")
- Explore the CEPS EurLex dataset (e.g. "How many acts are there?",
  "Show me acts about environmental protection")

Keep your response under 300 characters. Be conversational and helpful.

User message: {message}

Response:"""


class GreetingAgent:
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

    def answer(self, message: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        prompt = GREETING_PROMPT.format(message=message.strip()[:500])
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 300,
        }

        for attempt in range(2):
            try:
                resp = httpx.post(
                    self._endpoint, headers=headers, json=payload, timeout=15.0
                )
            except httpx.HTTPError:
                time.sleep(1)
                continue

            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                return {
                    "answer": text,
                    "sources": [],
                    "warnings": [],
                    "disclaimer": "",
                    "grounded": True,
                    "ungrounded_celex": [],
                    "model": "greeting-agent",
                    "intent": "greeting",
                }

            if resp.status_code == 429:
                time.sleep(2)
                continue
            break

        return {
            "answer": (
                "Hello! I can help you with questions about EU regulations or "
                "explore the CEPS EurLex dataset. What would you like to know?"
            ),
            "sources": [],
            "warnings": [],
            "disclaimer": "",
            "grounded": True,
            "ungrounded_celex": [],
            "model": "",
            "intent": "greeting",
        }


_greeting_agent: GreetingAgent | None = None


def get_greeting_agent() -> GreetingAgent:
    global _greeting_agent
    if _greeting_agent is None:
        _greeting_agent = GreetingAgent()
    return _greeting_agent
