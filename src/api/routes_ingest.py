"""Ingestion route: /ingest (admin-only, §8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.auth.dependencies import get_current_admin
from src.ingestion import embed_and_index, pipeline

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
def ingest(
    user: dict = Depends(get_current_admin),
    sample: int | None = Query(default=None, ge=1, help="Limit rows for smoke test"),
    embed_limit: int | None = Query(
        default=None, ge=1, help="Limit number of chunks to embed"
    ),
):
    """Run the M1 cleaning+chunking pipeline then M2 embedding. Admin only."""
    stats = pipeline.ingest(sample=sample)
    estats = embed_and_index.embed_index(limit=embed_limit)
    if estats.chunks_upserted == 0 and stats.chunks_produced == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ingestion produced no chunks")
    return {
        "status": "ok",
        "ingestion": {
            "rows_seen": stats.rows_seen,
            "rows_kept": stats.rows_kept,
            "rows_dropped": stats.rows_dropped,
            "chunks_produced": stats.chunks_produced,
            "drop_reasons": stats.drop_reasons,
        },
        "embedding": {
            "chunks_seen": estats.chunks_seen,
            "chunks_upserted": estats.chunks_upserted,
            "batches": estats.batches,
        },
    }
