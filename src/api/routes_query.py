"""Query, acts, history, and feedback routes (§8, §9.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src import config
from src.api.schemas import (
    FeedbackRequest,
    QueryRequest,
    QueryResponse,
    Source,
)
from src.auth import models
from src.auth.dependencies import get_current_user
from src.generation import orchestrator

router = APIRouter(tags=["query"])


def _filters_to_dict(req: QueryRequest) -> dict[str, Any] | None:
    if req.filters is None:
        return None
    d = req.filters.model_dump(exclude_none=True)
    return d or None


@router.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    user: dict = Depends(get_current_user),
):
    filters = _filters_to_dict(req)
    result = orchestrator.answer_question(
        req.question,
        top_k=req.top_k or config.DEFAULT_TOP_K,
        filters=filters,
        include_repealed=req.include_repealed,
        session_id=f"regcom-user-{user['id']}",
        dataset_ids=req.dataset_ids,
        document_ids=req.document_ids,
        celex_ids=req.celex_ids,
        language=req.language,
    )
    # --- audit log (§9.3) ---------------------------------------------------
    conn = models.get_db()
    try:
        qid = models.log_query(
            conn,
            user_id=user["id"],
            question=req.question,
            answer=result["answer"],
            sources=result["sources"],
            grounded=result["grounded"],
            model=result.get("model"),
        )
    finally:
        conn.close()
    result["query_log_id"] = qid
    return QueryResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        warnings=result["warnings"],
        disclaimer=result["disclaimer"],
        grounded=result["grounded"],
        ungrounded_celex=result["ungrounded_celex"],
        model=result.get("model", ""),
        query_log_id=qid,
    )


@router.get("/history")
def history(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
):
    conn = models.get_db()
    try:
        return models.get_history(conn, user["id"], limit=limit)
    finally:
        conn.close()


@router.delete("/history/{query_log_id}", status_code=status.HTTP_200_OK)
def delete_history(
    query_log_id: int,
    user: dict = Depends(get_current_user),
):
    conn = models.get_db()
    try:
        deleted = models.delete_query_log(conn, user["id"], query_log_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Query log entry not found")
    return {"id": query_log_id, "status": "deleted"}


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def feedback(
    req: FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    conn = models.get_db()
    try:
        fid = models.add_feedback(
            conn,
            user_id=user["id"],
            query_log_id=req.query_log_id,
            rating=req.rating,
            comment=req.comment,
        )
    finally:
        conn.close()
    return {"id": fid, "status": "recorded"}
