"""Assemble the message list sent to the LLM (§5.5).

Builds:
- ``system`` message: the versioned prompt body from ``prompts/system_prompt.md``
  with the per-query CONTEXT block (chunk metadata + text) appended.
- ``user`` message: the raw question.

The system prompt file is loaded once and cached; it is *not* templated beyond
the embedded CONTEXT (no Jinja etc.), so the only thing that changes per query
is the CONTEXT chunk list. Keeping the prompt in a versioned file (§5.5) means
disclaimer / instruction tweaks are a one-line file edit, never a code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src import config

# Supported answer languages (code -> human name shown in the prompt).
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "vi": "Vietnamese",
}
DEFAULT_LANGUAGE = "en"


class PromptBuilder:
    def __init__(self, system_prompt_path: Path = config.SYSTEM_PROMPT_PATH) -> None:
        self._path = system_prompt_path
        self._cached: str | None = None

    @property
    def system_prompt_body(self) -> str:
        if self._cached is None:
            if not self._path.exists():
                raise FileNotFoundError(f"system prompt not found: {self._path}")
            self._cached = self._path.read_text(encoding="utf-8")
        return self._cached

    def build_context_block(self, chunks: list[dict[str, Any]]) -> str:
        if not chunks:
            return "[No context chunks were retrieved for this query.]"
        parts: list[str] = []
        for i, c in enumerate(chunks):
            meta = c.get("metadata") or {}
            parts.append(
                "[CHUNK {idx}] dataset={dataset} | celex={celex} | act_name={act} "
                "| file={file} | status={status} | temporal_status={temp} "
                "| link={link}\n{text}".format(
                    idx=i,
                    dataset=meta.get("dataset_name", ""),
                    celex=meta.get("celex", ""),
                    act=meta.get("act_name", ""),
                    file=meta.get("filename", ""),
                    status=meta.get("status", ""),
                    temp=meta.get("temporal_status", ""),
                    link=meta.get("eurlex_link", ""),
                    text=(c.get("text") or "").strip(),
                )
            )
        return "\n\n".join(parts)

    def build_messages(
        self,
        question: str,
        chunks: list[dict[str, Any]],
        language: str | None = None,
    ) -> list[dict[str, str]]:
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string")
        system_text = (
            self.system_prompt_body
            + "\n\n# CONTEXT (for this query)\n\n"
            + self.build_context_block(chunks)
        )
        language_name = LANGUAGE_NAMES.get(
            (language or DEFAULT_LANGUAGE).lower(), LANGUAGE_NAMES[DEFAULT_LANGUAGE]
        )
        system_text += (
            f"\n\n# LANGUAGE\nWrite the entire answer in {language_name}. "
            "Keep CELEX numbers, act titles, and links unchanged."
        )
        return [
            {"role": "system", "content": system_text},
            {"role": "user", "content": question.strip()},
        ]


def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()
