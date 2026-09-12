"""Q&A agent — wraps the existing hybrid retrieval + generation pipeline."""

from __future__ import annotations

from typing import Any

from src import config
from src.api.schemas import QueryRequest
from src.generation import orchestrator


class QAAgent:
    def answer(self, question: str, user_id: int, **kwargs: Any) -> dict[str, Any]:
        req = QueryRequest(
            question=question,
            filters=kwargs.get("filters"),
            include_repealed=bool(kwargs.get("include_repealed")),
            top_k=kwargs.get("top_k"),
            dataset_ids=kwargs.get("dataset_ids"),
            document_ids=kwargs.get("document_ids"),
            celex_ids=kwargs.get("celex_ids"),
        )
        filters = req.filters.model_dump(exclude_none=True) if req.filters else None
        result = orchestrator.answer_question(
            question=req.question,
            top_k=req.top_k or config.DEFAULT_TOP_K,
            filters=filters or None,
            include_repealed=req.include_repealed,
            session_id=kwargs.get("session_id"),
            dataset_ids=req.dataset_ids,
            document_ids=req.document_ids,
            celex_ids=req.celex_ids,
        )
        if result is None:
            return {
                "answer": "Sorry, I could not find relevant information to answer your question.",
                "sources": [],
                "warnings": [],
                "disclaimer": "",
                "grounded": False,
                "ungrounded_celex": [],
                "model": "",
                "query_log_id": None,
                "intent": "question",
            }
        return {**result, "intent": "question"}


_qa_agent: QAAgent | None = None


def get_qa_agent() -> QAAgent:
    global _qa_agent
    if _qa_agent is None:
        _qa_agent = QAAgent()
    return _qa_agent
