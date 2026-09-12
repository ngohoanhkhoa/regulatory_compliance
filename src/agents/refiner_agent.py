"""Response Refiner Agent — polishes error responses into helpful user-facing messages.

When the Q&A or Explore agent returns an error/empty result, this agent rewrites
the response to be more helpful: explains what went wrong, suggests alternative
questions, and guides the user toward productive interactions.
"""

from __future__ import annotations

import time

import httpx

from src import config

REFINER_PROMPT = """\
You are a helpful assistant for an EU regulatory compliance chatbot. The system \
just tried to answer a user's question but encountered a problem. Your job is to \
rewrite the system's raw response into a helpful, user-friendly message.

Rules:
- If the raw answer is empty, confusing, or an error, explain politely what might \
  have gone wrong.
- Suggest 2-3 alternative questions the user could ask instead, based on their \
  original question.
- Keep the tone friendly and constructive. Do NOT mention "the agent", "the system", \
  or internal details.
- If the raw answer is actually fine (has real content), return it unchanged.
- Format suggestions as a short bullet list.
- Keep the entire response under 500 characters.

User's original question: {question}
Raw system response: {raw_answer}

Helpful response:"""


class RefinerAgent:
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

    def refine(self, question: str, raw_answer: str) -> str:
        needs_refinement = self._needs_refinement(raw_answer)
        if not needs_refinement:
            return raw_answer

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        prompt = REFINER_PROMPT.format(
            question=question.strip()[:1000],
            raw_answer=raw_answer.strip()[:1500],
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 400,
        }

        for attempt in range(2):
            try:
                resp = httpx.post(
                    self._endpoint, headers=headers, json=payload, timeout=20.0
                )
            except httpx.HTTPError:
                time.sleep(1)
                continue

            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                return content if content else raw_answer

            if resp.status_code == 429:
                time.sleep(2)
                continue
            break

        return raw_answer

    @staticmethod
    def _needs_refinement(answer: str) -> bool:
        if not answer or not answer.strip():
            return True
        a = answer.lower()
        indicators = [
            "could not",
            "no act found",
            "no acts match",
            "not available",
            "sorry",
            "could not compute",
            "could not count",
            "could not group",
            "could not list",
            "could not search",
            "could not describe",
            "no supporting sources",
            "i could not find",
            "please provide",
        ]
        for phrase in indicators:
            if phrase in a:
                return True
        if len(answer) < 50 and "match" not in a:
            return True
        return False


_refiner: RefinerAgent | None = None


def get_refiner() -> RefinerAgent:
    global _refiner
    if _refiner is None:
        _refiner = RefinerAgent()
    return _refiner


def refine_response(question: str, raw_answer: str) -> str:
    return get_refiner().refine(question, raw_answer)
