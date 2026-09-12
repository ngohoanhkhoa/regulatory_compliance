"""Unified /chat endpoint that routes through the multi-agent system."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.agents.explore_agent import get_explore_agent
from src.agents.greeting_agent import get_greeting_agent
from src.agents.intent_router import classify_intent
from src.agents.qa_agent import get_qa_agent
from src.agents.refiner_agent import refine_response
from src.api.schemas import QueryRequest, QueryResponse
from src.auth.dependencies import get_current_user
from src.auth.models import get_db, log_query

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=QueryResponse)
def chat(request: QueryRequest, user: dict = Depends(get_current_user)):
    intent = classify_intent(request.question)

    # Corpus exploration is EURLEX-specific; when the user has explicitly scoped
    # the chat to datasets, answer through retrieval so the selected datasets are
    # actually used.
    if intent == "explore" and request.dataset_ids:
        intent = "question"

    if intent == "greeting":
        agent = get_greeting_agent()
        result = agent.answer(request.question)
    elif intent == "explore":
        agent = get_explore_agent()
        result = agent.answer(request.question)
    else:
        agent = get_qa_agent()
        result = agent.answer(
            request.question,
            user_id=user["id"],
            filters=request.filters,
            top_k=request.top_k,
            include_repealed=request.include_repealed,
            dataset_ids=request.dataset_ids,
            document_ids=request.document_ids,
            # Stable per-user session id for OpenCode Go routing/prompt caching.
            session_id=f"regcom-user-{user['id']}",
        )

    refined_answer = refine_response(request.question, result.get("answer", ""))
    result["answer"] = refined_answer

    conn = get_db()
    qid: int | None = None
    try:
        qid = log_query(
            conn,
            user_id=user["id"],
            question=request.question,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            grounded=bool(result.get("grounded")),
            model=result.get("model", ""),
        )
    finally:
        conn.close()

    return QueryResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        warnings=result.get("warnings", []),
        disclaimer=result.get("disclaimer", ""),
        grounded=bool(result.get("grounded")),
        ungrounded_celex=result.get("ungrounded_celex", []),
        model=result.get("model", ""),
        query_log_id=qid,
        intent=intent,
    )
