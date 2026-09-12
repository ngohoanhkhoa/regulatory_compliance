"""Generation pipeline: retrieve -> prompt -> LLM -> citations -> warnings (§5.5, §8).

This is the orchestration layer the FastAPI `/query` route (M5) will call. It
keeps all the messy bits in one place so the API route is a thin adapter:

    result = answer_question("Is GDPR still in force?")

returns a dict matching the §8 response schema:

    {
      "answer": str,
      "sources": [{celex, act_name, status, link, chunk_excerpt}, ...],
      "warnings": [str, ...],
      "disclaimer": "Not legal advice.",
      "grounded": bool,
      "ungrounded_celex": [str, ...],
    }

Warnings always include the dataset cutoff disclosure (§9.4). The disclaimer is
served from the central config so the UI and the answer body stay in sync.
"""

from __future__ import annotations

from typing import Any

from src import config
from src.generation import citation_formatter as cf
from src.generation import llm_client, prompt_builder
from src.retrieval import hybrid_retriever


def _default_disclaimer() -> str:
    return (
        "Not legal advice. The underlying dataset is frozen at "
        f"{config.DATA_CUTOFF_DATE}; verify against current eur-lex.eu before acting. "
        "[PROVISIONAL DISCLAIMER — pending review by a lawyer before real-world use.]"
    )


def _in_force_warnings(retrieved: list[dict]) -> list[str]:
    warnings: list[str] = []
    for c in retrieved:
        meta = c.get("metadata") or {}
        status = str(meta.get("status") or "").strip()
        if status and status.lower() not in ("in force", ""):
            warnings.append(
                f"Cited act {meta.get('celex', '?')} ({meta.get('act_name', '?')}) "
                f"is marked '{status}'."
            )
    return warnings


def answer_question(
    question: str,
    *,
    retrieved: list[dict] | None = None,
    llm: llm_client.LLMClient | None = None,
    top_k: int = config.DEFAULT_TOP_K,
    filters: dict[str, Any] | None = None,
    include_repealed: bool = False,
    session_id: str | None = None,
    dataset_ids: list[int] | None = None,
    document_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Produce a fully-cited answer for `question`."""
    if retrieved is None:
        if dataset_ids:
            from src.retrieval import dataset_retriever

            retrieved = dataset_retriever.retrieve(
                question,
                dataset_ids,
                top_k=top_k,
                filters=filters,
                include_repealed=include_repealed,
                document_ids=document_ids,
            )
        else:
            retrieved = hybrid_retriever.retrieve(
                question, top_k=top_k, filters=filters, include_repealed=include_repealed
            )
    builder = prompt_builder.get_prompt_builder()
    messages = builder.build_messages(question, retrieved)
    llm = llm or llm_client.get_llm_client()
    response = llm.complete(messages, session_id=session_id)
    answer_text = response.text

    sources = cf.build_sources(retrieved)
    grounding = cf.check_grounding(answer_text, retrieved)

    warnings: list[str] = [
        f"Dataset frozen at {config.DATA_CUTOFF_DATE} — recent legislation may be missing; "
        "verify on eur-lex.eu."
    ]
    warnings.extend(_in_force_warnings(retrieved))
    if not grounding.grounded:
        warnings.append(
            "Answer references CELEX number(s) not present in retrieved context: "
            + ", ".join(grounding.ungrounded)
        )
    if not sources:
        warnings.append("No supporting sources retrieved for this question.")

    return {
        "answer": answer_text,
        "sources": sources,
        "warnings": warnings,
        "disclaimer": _default_disclaimer(),
        "grounded": grounding.grounded,
        "ungrounded_celex": grounding.ungrounded,
        "model": response.model,
    }
