"""Topic timeline service: match acts to a topic and order them by date.

A topic stores a natural-language ``search_query`` (defaults to its name), an
optional set of metadata ``filters`` and an ``include_repealed`` flag. We reuse
the existing hybrid retriever to find relevant chunks, then de-duplicate by
CELEX so each act appears once on the timeline, keeping its best-scoring chunk.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src import config
from src.generation import llm_client
from src.retrieval import hybrid_retriever
from src.topics import summarizer

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d-%m-%Y",
    "%Y%m%d",
)


def _date_sort_key(value: str | None) -> str:
    """Return an ISO date string for sorting; unparseable dates sort last."""
    raw = (value or "").strip()
    if not raw:
        return "9999-99-99"
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return f"9999-{raw}"


def _topic_query(topic: dict[str, Any]) -> str:
    """The retrieval query for a topic.

    An explicit ``search_query`` wins; otherwise combine the topic name and
    description so the default search reflects both.
    """
    explicit = (topic.get("search_query") or "").strip()
    if explicit:
        return explicit
    parts = [
        (topic.get("name") or "").strip(),
        (topic.get("description") or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def _item_from_hit(hit: dict[str, Any]) -> dict[str, Any] | None:
    meta = hit.get("metadata") or {}
    celex = str(meta.get("celex") or "").strip()
    if not celex:
        return None
    score = float(hit.get("rerank_score") or hit.get("score") or 0.0)
    return {
        "celex": celex,
        "act_name": str(meta.get("act_name") or ""),
        "status": str(meta.get("status") or ""),
        "date_document": str(meta.get("date_document") or ""),
        "temporal_status": str(meta.get("temporal_status") or ""),
        "eurovoc": str(meta.get("eurovoc") or ""),
        "subject_matter": str(meta.get("subject_matter") or ""),
        "link": str(meta.get("eurlex_link") or ""),
        "excerpt": (hit.get("text") or "").strip()[:400],
        "score": round(score, 4),
    }


def build_timeline(
    topic: dict[str, Any],
    *,
    top_k: int | None = None,
    retrieved: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return one de-duplicated, date-sorted timeline item per matching act.

    ``retrieved`` can be injected for tests; otherwise the hybrid retriever is
    called with the topic's query/filters.
    """
    top_k = top_k or config.TOPIC_TIMELINE_K

    if retrieved is None:
        query = _topic_query(topic)
        retrieved = hybrid_retriever.retrieve(
            query,
            top_k=top_k,
            n_candidates=max(top_k, config.RERANK_CANDIDATE_K),
            filters=topic.get("filters") or None,
            include_repealed=bool(topic.get("include_repealed")),
        )

    by_celex: dict[str, dict[str, Any]] = {}
    for hit in retrieved:
        item = _item_from_hit(hit)
        if item is None:
            continue
        current = by_celex.get(item["celex"])
        if current is None or item["score"] > current["score"]:
            by_celex[item["celex"]] = item

    # Newest → oldest. Two passes keep the CELEX tiebreak ascending for equal
    # dates regardless of the reverse date sort.
    ordered = sorted(by_celex.values(), key=lambda i: i["celex"])
    ordered.sort(key=lambda i: _date_sort_key(i["date_document"]), reverse=True)
    return ordered


def refresh_topic_timeline(
    topic: dict[str, Any],
    *,
    llm: llm_client.LLMClient | None = None,
    retrieved: list[dict[str, Any]] | None = None,
    previous_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve acts for ``topic`` and attach a per-act summary.

    Summaries already stored for a CELEX are reused; only newly found acts are
    summarised, so a refresh does not regenerate existing summaries. Returns
    newest-first items ready to be persisted. Summaries are best-effort: a
    failure leaves them empty without discarding the retrieved acts.
    """
    items = build_timeline(topic, retrieved=retrieved)

    summary_by_celex: dict[str, str] = {}
    for prev in previous_items or []:
        celex = str(prev.get("celex") or "")
        if celex and prev.get("summary"):
            summary_by_celex[celex] = str(prev["summary"])

    to_summarize = [i for i in items if not summary_by_celex.get(i["celex"])]
    if to_summarize:
        fresh = summarizer.summarize_items(
            topic.get("name") or "",
            to_summarize,
            llm=llm,
            session_id=f"regcom-topic-{topic.get('id')}",
        )
        for item, summary in zip(to_summarize, fresh):
            if summary:
                summary_by_celex[item["celex"]] = summary

    for item in items:
        item["summary"] = summary_by_celex.get(item["celex"], "")
    return items
