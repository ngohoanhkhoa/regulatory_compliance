"""Query, acts, history, and feedback routes (§8, §9.3)."""

from __future__ import annotations

from typing import Any

import polars as pl
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src import config
from src.api.schemas import (
    ActResponse,
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


@router.get("/acts/{celex}", response_model=ActResponse)
def get_act(celex: str):
    """Return full metadata + cleaned text for one act (§8).

    Reads directly from the raw CSV via polars lazy scan (cheap, no index
    needed) and returns the cleaned text.
    """
    from src.ingestion import clean_text, load_csv

    if not load_csv.validate_header() == []:
        pass  # header OK
    try:
        lf = load_csv._scan()
    except FileNotFoundError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Raw CSV not available")
    df = lf.filter(pl.col("CELEX") == celex).collect()
    if df.is_empty():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Act {celex} not found")
    row = df.row(0, named=True)
    text = clean_text.clean_text(row.get("act_raw_text") or "")
    return ActResponse(
        celex=row["CELEX"],
        act_name=row.get("Act_name"),
        status=row.get("Status"),
        act_type=row.get("Act_type"),
        date_document=row.get("Date_document"),
        temporal_status=row.get("Temporal_status"),
        eurovoc=row.get("EUROVOC"),
        subject_matter=row.get("Subject_matter"),
        authors=row.get("Authors"),
        treaty=row.get("Treaty"),
        eurlex_link=row.get("Eurlex_link"),
        eli_link=row.get("ELI_link"),
        text=text,
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
