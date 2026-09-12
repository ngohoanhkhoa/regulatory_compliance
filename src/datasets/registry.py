"""Dataset registry helpers: stats, collections, and slug management.

A dataset is either:
- ``kind="documents"`` — a user's single private collection of uploaded files, or
- ``kind="regulatory"`` — a shared regulatory-text collection (the built-in
  EURLEX one, or an imported bundle), visible read-only to every user.

The registry row (SQLite) is the source of truth; ``meta`` carries the physical
backing: the Chroma ``collection`` name and (for regulatory) the ``chunks_path``
that feeds BM25.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

import polars as pl

from src import config

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, fallback: str = "dataset") -> str:
    slug = _SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return slug or fallback


def unique_slug(conn: sqlite3.Connection, base: str) -> str:
    from src.auth import models

    slug = slugify(base)
    candidate = slug
    n = 2
    while models.get_dataset_by_slug(conn, candidate) is not None:
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def collection_of(dataset: dict[str, Any]) -> str:
    return str((dataset.get("meta") or {}).get("collection") or "")


def chunks_path_of(dataset: dict[str, Any]) -> Path | None:
    raw = (dataset.get("meta") or {}).get("chunks_path")
    return Path(raw) if raw else None


def _vector_count(collection: str) -> int | None:
    if not collection:
        return None
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(config.VECTOR_STORE_DIR))
        coll = client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )
        return int(coll.count())
    except Exception:
        return None


def dataset_stats(conn: sqlite3.Connection, dataset: dict[str, Any]) -> dict[str, Any]:
    """Return display counts for a dataset: items, chunks, vectors."""
    from src.auth import models

    kind = dataset.get("kind")
    stats: dict[str, Any] = {"items": 0, "chunks": 0, "vectors": None}

    if kind == "documents":
        owner = dataset.get("owner_user_id")
        docs = models.list_documents(conn, int(owner)) if owner is not None else []
        stats["items"] = len(docs)
        stats["chunks"] = sum(int(d.get("num_chunks") or 0) for d in docs)
        stats["vectors"] = stats["chunks"]
        return stats

    path = chunks_path_of(dataset)
    if path and path.exists():
        try:
            df = pl.read_parquet(path)
            if "celex" in df.columns:
                stats["items"] = int(df["celex"].n_unique())
            stats["chunks"] = int(df.height)
        except Exception:
            pass
    stats["vectors"] = _vector_count(collection_of(dataset))
    return stats


def serialize(conn: sqlite3.Connection, dataset: dict[str, Any]) -> dict[str, Any]:
    """Dataset row + stats, JSON-ready for the API."""
    stats = dataset_stats(conn, dataset)
    return {
        "id": int(dataset["id"]),
        "name": dataset["name"],
        "slug": dataset["slug"],
        "description": dataset.get("description", ""),
        "kind": dataset["kind"],
        "source": dataset["source"],
        "status": dataset.get("status", "ready"),
        "owner_user_id": dataset.get("owner_user_id"),
        "is_global": dataset.get("owner_user_id") is None,
        "created_at": dataset.get("created_at"),
        "updated_at": dataset.get("updated_at"),
        "items": stats["items"],
        "chunks": stats["chunks"],
        "vectors": stats["vectors"],
    }
