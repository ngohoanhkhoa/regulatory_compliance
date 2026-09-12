"""Read-only views over a regulatory corpus (per-dataset chunk parquet).

The corpus lives in the chunk parquet plus its Chroma collection; both are
managed at the *dataset* level by ``src.datasets`` (import/export/remove). This
module exposes the read helpers used by the datasets API:

- a canonical, sortable, paginated item listing (``list_acts``), and
- one item's full content (``get_item``).

Columns are mapped through ``src.corpus.schema`` so any regulatory dataset
(not just the CEPS/EURLEX export) renders with the same canonical fields. The
grouped item frame is cached in-process keyed by file path + mtime, so paging
and sorting don't re-scan a large parquet on every request.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import polars as pl

from src import config
from src.corpus import schema

# path -> (mtime, grouped frame, resolved columns)
_CACHE: dict[str, tuple[float, pl.DataFrame, dict[str, str]]] = {}
_CACHE_LOCK = threading.Lock()

DEFAULT_LIMIT = 25
_MAX_LIMIT = 500


def _load_chunks(path: Path | None = None) -> pl.DataFrame:
    path = path or config.PROCESSED_CHUNKS_PATH
    if not path.exists():
        return pl.DataFrame()
    return pl.read_parquet(path)


def clear_cache(path: Path | None = None) -> None:
    """Drop the cached item frame (all datasets, or one path)."""
    with _CACHE_LOCK:
        if path is None:
            _CACHE.clear()
        else:
            _CACHE.pop(str(path), None)


def _with_item_id(df: pl.DataFrame, resolved: dict[str, str]) -> pl.DataFrame:
    """Add a ``_id`` column: resolved id column, else the chunk_id prefix."""
    if "id" in resolved:
        return df.with_columns(
            pl.col(resolved["id"]).cast(pl.Utf8).alias("_id")
        )
    if schema.ID_FALLBACK in df.columns:
        return df.with_columns(
            pl.col(schema.ID_FALLBACK)
            .cast(pl.Utf8)
            .str.split(schema.ID_SEPARATOR)
            .list.first()
            .alias("_id")
        )
    return df.with_row_index("_id").with_columns(pl.col("_id").cast(pl.Utf8))


def _grouped(path: Path | None = None) -> tuple[pl.DataFrame, dict[str, str]]:
    """Return (grouped item frame, resolved columns), using the cache."""
    p = path or config.PROCESSED_CHUNKS_PATH
    if not p.exists():
        return pl.DataFrame(), {}
    key = str(p)
    mtime = p.stat().st_mtime
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]

    df = pl.read_parquet(p)
    if df.is_empty():
        frame = pl.DataFrame()
        resolved: dict[str, str] = {}
    else:
        resolved = schema.resolve_columns(list(df.columns))
        df = _with_item_id(df, resolved)
        aggs = []
        for field in ("title", "status", "date", "type"):
            if field in resolved:
                aggs.append(
                    pl.col(resolved[field]).first().cast(pl.Utf8).alias(field)
                )
        aggs.append(pl.len().alias("chunks"))
        frame = df.group_by("_id").agg(aggs).rename({"_id": "id"})

    with _CACHE_LOCK:
        _CACHE[key] = (mtime, frame, resolved)
    return frame, resolved


def _resolve_sort(
    sort: str | None, order: str | None, columns: list[str]
) -> tuple[str | None, str]:
    allowed = [k for k, _ in schema.CANONICAL_FIELDS if k in columns]
    if not allowed:
        return None, "desc"
    if sort in allowed:
        key = sort
    elif "date" in allowed:
        key = "date"
    elif "id" in allowed:
        key = "id"
    else:
        key = allowed[0]
    if order in ("asc", "desc"):
        resolved_order = order
    else:
        resolved_order = "desc" if key in ("date", "chunks") else "asc"
    return key, resolved_order


def list_acts(
    path: Path | None = None,
    query: str = "",
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    sort: str | None = None,
    order: str | None = None,
) -> dict[str, Any]:
    """Canonical, searchable, sortable, paginated item listing."""
    frame, resolved = _grouped(path)
    columns = schema.descriptor(resolved, list(frame.columns) if not frame.is_empty() else [])
    key, resolved_order = _resolve_sort(sort, order, list(frame.columns))

    if frame.is_empty():
        return {
            "items": [],
            "total": 0,
            "columns": columns,
            "sort": key,
            "order": resolved_order,
            "limit": limit,
            "offset": offset,
        }

    view = frame
    q = (query or "").strip().lower()
    if q:
        cond = None
        for field in ("id", "title", "status"):
            if field in view.columns:
                part = pl.col(field).fill_null("").str.to_lowercase().str.contains(
                    q, literal=True
                )
                cond = part if cond is None else (cond | part)
        if cond is not None:
            view = view.filter(cond)

    total = int(view.height)
    if key is not None:
        view = view.sort(key, descending=(resolved_order == "desc"), nulls_last=True)

    limit = max(1, min(int(limit), _MAX_LIMIT))
    page = view.slice(int(offset), limit)
    return {
        "items": page.to_dicts(),
        "total": total,
        "columns": columns,
        "sort": key,
        "order": resolved_order,
        "limit": limit,
        "offset": offset,
    }


_BODY_COLUMNS = frozenset(
    {
        "chunk_text",
        "chunk_id",
        "chunk_index",
        "boundary",
        "char_offset_start",
        "char_offset_end",
    }
)


def get_item(path: Path | None = None, item_id: str = "") -> dict[str, Any]:
    """Return one item's canonical metadata, extra fields, and ordered chunks."""
    p = path or config.PROCESSED_CHUNKS_PATH
    if not p.exists():
        raise FileNotFoundError(str(p))

    lf = pl.scan_parquet(p)
    cols = list(lf.collect_schema().names())
    resolved = schema.resolve_columns(cols)
    item_id = str(item_id)

    if "id" in resolved:
        cond = pl.col(resolved["id"]).cast(pl.Utf8) == item_id
    elif schema.ID_FALLBACK in cols:
        cond = pl.col(schema.ID_FALLBACK).cast(pl.Utf8).str.starts_with(
            item_id + schema.ID_SEPARATOR
        )
    else:
        raise KeyError(item_id)

    df = lf.filter(cond).collect()
    if df.is_empty():
        raise KeyError(item_id)
    if "chunk_index" in df.columns:
        df = df.sort("chunk_index", nulls_last=True, descending=False)

    rows = df.to_dicts()
    first = rows[0]

    item: dict[str, Any] = {"id": item_id}
    for field in ("title", "status", "date", "type"):
        if field in resolved:
            value = first.get(resolved[field])
            item[field] = "" if value is None else str(value)

    exclude = set(_BODY_COLUMNS) | set(resolved.values())
    fields: dict[str, Any] = {}
    for col in df.columns:
        if col in exclude:
            continue
        value = first.get(col)
        if value not in (None, ""):
            fields[col] = str(value)

    chunks = []
    for i, row in enumerate(rows):
        idx = row.get("chunk_index")
        chunks.append(
            {
                "chunk_index": int(idx) if idx is not None else i,
                "boundary": str(row.get("boundary") or ""),
                "text": str(row.get("chunk_text") or ""),
            }
        )

    item["fields"] = fields
    item["chunks"] = chunks
    return item


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


def ingestion_log() -> dict[str, Any] | None:
    if not config.INGESTION_LOG_PATH.exists():
        return None
    try:
        return json.loads(config.INGESTION_LOG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
