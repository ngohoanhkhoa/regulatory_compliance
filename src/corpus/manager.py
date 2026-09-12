"""Read-only views over a regulatory corpus (per-dataset chunk parquet).

The corpus lives in the chunk parquet plus its Chroma collection; both are
managed at the *dataset* level by ``src.datasets`` (import/export/remove). This
module only exposes read helpers used by the datasets API: aggregate stats and a
SEARCHABLE act listing. The in-process BM25 index is rebuilt from the parquet on
every retrieval, so it reflects edits without extra work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from src import config


def _load_chunks(path: Path | None = None) -> pl.DataFrame:
    path = path or config.PROCESSED_CHUNKS_PATH
    if not path.exists():
        return pl.DataFrame()
    return pl.read_parquet(path)


def corpus_stats(path: Path | None = None) -> dict[str, Any]:
    df = _load_chunks(path)
    acts = chunks = 0
    by_status: list[dict[str, Any]] = []
    if not df.is_empty() and "celex" in df.columns:
        acts = int(df["celex"].n_unique())
        chunks = int(df.height)
        if "status" in df.columns:
            counts = df.group_by("status").len().sort("len", descending=True)
            by_status = [
                {"status": str(r.get("status") or "(unknown)"), "count": int(r["len"])}
                for r in counts.to_dicts()
            ]
    return {
        "acts": acts,
        "chunks": chunks,
        "by_status": by_status,
        "data_cutoff_date": config.DATA_CUTOFF_DATE,
    }


def list_acts(
    path: Path | None = None,
    query: str = "",
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    df = _load_chunks(path)
    if df.is_empty() or "celex" not in df.columns:
        return {"items": [], "total": 0}

    agg = [
        pl.first("act_name").alias("act_name"),
        pl.first("status").alias("status"),
        pl.first("date_document").alias("date_document"),
        pl.first("eurovoc").alias("eurovoc"),
        pl.first("subject_matter").alias("subject_matter"),
        pl.first("eurlex_link").alias("eurlex_link"),
        pl.len().alias("chunk_count"),
    ]
    grouped = df.group_by("celex").agg(agg)

    q = (query or "").strip().lower()
    if q:
        grouped = grouped.filter(
            pl.col("celex").fill_null("").str.to_lowercase().str.contains(q, literal=True)
            | pl.col("act_name").fill_null("").str.to_lowercase().str.contains(q, literal=True)
            | pl.col("status").fill_null("").str.to_lowercase().str.contains(q, literal=True)
        )

    grouped = grouped.sort("date_document", descending=True, nulls_last=True)
    total = int(grouped.height)
    page = grouped.slice(int(offset), int(limit))
    return {"items": page.to_dicts(), "total": total}


def ingestion_log() -> dict[str, Any] | None:
    if not config.INGESTION_LOG_PATH.exists():
        return None
    try:
        return json.loads(config.INGESTION_LOG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
