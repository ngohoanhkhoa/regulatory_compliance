"""Per-act summariser for topic timelines.

Given a topic and the acts retrieved for it, ask the main OpenCode Go model for
one concise sentence per act explaining how it links to the topic. A single
batched call keeps a refresh to two LLM requests total (rerank + summary);
failures degrade to empty summaries rather than breaking the refresh.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.generation import llm_client

SUMMARY_PROMPT = """\
You are a regulatory analyst. A user follows the EU regulatory topic: "{topic}".

For each legal act below, write ONE concise sentence (max ~30 words) explaining \
how the act relates to the topic. Base it only on the act's excerpt; do not \
invent details. If the excerpt gives no clear link to the topic, write exactly: \
"No clear link to the topic."

Return ONLY a JSON array of strings, one entry per act, in the same order as \
listed. Do not add numbering, markdown, or any text outside the JSON array.

Acts:
{acts}
"""


def _format_acts(items: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, item in enumerate(items):
        excerpt = (item.get("excerpt") or "").strip()[:600]
        blocks.append(
            f"[{i}] {item.get('celex', '')} — {item.get('act_name', '')}\n"
            f"Date: {item.get('date_document', '')} | Status: {item.get('status', '')}\n"
            f"Excerpt: {excerpt or '(no excerpt available)'}"
        )
    return "\n\n".join(blocks)


def _parse_summaries(text: str, expected: int) -> list[str]:
    empty = ["" for _ in range(expected)]
    if not text:
        return empty
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return empty
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return empty
    if not isinstance(data, list):
        return empty
    out = [str(x).strip() if isinstance(x, str) else "" for x in data]
    if len(out) < expected:
        out += ["" for _ in range(expected - len(out))]
    return out[:expected]


def summarize_items(
    topic_name: str,
    items: list[dict[str, Any]],
    *,
    llm: llm_client.LLMClient | None = None,
    session_id: str | None = None,
) -> list[str]:
    """Return one summary string per item (empty string on failure)."""
    if not items:
        return []

    llm = llm or llm_client.get_llm_client()
    messages = [
        {"role": "system", "content": "You are a concise legal analyst. Reply with JSON only."},
        {
            "role": "user",
            "content": SUMMARY_PROMPT.format(
                topic=(topic_name or "").strip()[:200],
                acts=_format_acts(items),
            ),
        },
    ]
    try:
        response = llm.complete(messages, temperature=0.0, session_id=session_id)
    except llm_client.LLMError:
        return ["" for _ in items]
    return _parse_summaries(response.text, len(items))
