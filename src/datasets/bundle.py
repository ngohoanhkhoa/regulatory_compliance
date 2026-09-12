"""Dataset import/export bundles (``.rcdataset.zip``).

A regulatory bundle carries the processed texts so a recipient can add the whole
dataset to their instance without re-running the CSV pipeline::

    manifest.json    # format/version, type, name, slug, counts, embedding info
    chunks.parquet   # M1 chunk store (all processed texts)
    embeddings.npy   # optional, row-aligned to the parquet — skips re-embedding

Document datasets export their original source files only (private to the owner).
"""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from src import config
from src.auth import models
from src.datasets import registry

MANIFEST_NAME = "manifest.json"
CHUNKS_NAME = "chunks.parquet"
EMBEDDINGS_NAME = "embeddings.npy"

_META_FIELDS = (
    "celex",
    "chunk_index",
    "boundary",
    "status",
    "date_document",
    "temporal_status",
    "eurovoc",
    "subject_matter",
    "eurlex_link",
    "act_name",
)


class DatasetBundleError(ValueError):
    """Raised for malformed or unsupported dataset bundles."""


def _collection_client():
    import chromadb

    config.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(config.VECTOR_STORE_DIR))


def _load_chroma_embeddings(dataset: dict[str, Any]) -> np.ndarray | None:
    """Read embeddings for a regulatory dataset in parquet order (or None)."""
    path = registry.chunks_path_of(dataset)
    collection = registry.collection_of(dataset)
    if not path or not path.exists() or not collection:
        return None
    df = pl.read_parquet(path)
    ids = [str(x) for x in df["chunk_id"].to_list()]
    if not ids:
        return None
    coll = _collection_client().get_or_create_collection(
        name=collection, metadata={"hnsw:space": "cosine"}
    )
    by_id: dict[str, list[float]] = {}
    batch = 2000
    for start in range(0, len(ids), batch):
        got = coll.get(ids=ids[start : start + batch], include=["embeddings"])
        got_ids = got.get("ids") or []
        got_emb = got.get("embeddings")
        if got_emb is None:
            return None
        for i, cid in enumerate(got_ids):
            by_id[str(cid)] = list(got_emb[i])
    ordered = [by_id.get(cid) for cid in ids]
    if any(v is None for v in ordered):
        return None
    return np.asarray(ordered, dtype="float32")


def _manifest(dataset: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict:
    manifest: dict[str, Any] = {
        "format": "regcomp-dataset",
        "version": config.DATASET_BUNDLE_VERSION,
        "type": dataset.get("kind"),
        "name": dataset.get("name"),
        "slug": dataset.get("slug"),
        "description": dataset.get("description", ""),
        "source": dataset.get("source"),
        "data_cutoff_date": config.DATA_CUTOFF_DATE,
        "embedding_model": config.OPENROUTER_EMBEDDING_MODEL,
    }
    if extra:
        manifest.update(extra)
    return manifest


def export_dataset(
    dataset: dict[str, Any], *, include_embeddings: bool = True
) -> tuple[str, bytes]:
    """Return ``(filename, zip_bytes)`` for a dataset."""
    kind = dataset.get("kind")
    buf = io.BytesIO()

    if kind == "regulatory":
        path = registry.chunks_path_of(dataset)
        if not path or not path.exists():
            raise DatasetBundleError("Dataset chunks file is missing.")
        df = pl.read_parquet(path)
        manifest = _manifest(
            dataset,
            extra={"num_chunks": int(df.height), "chunk_schema": list(df.columns)},
        )
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(path, CHUNKS_NAME)
            if include_embeddings:
                embeddings = _load_chroma_embeddings(dataset)
                if embeddings is not None:
                    npy = io.BytesIO()
                    np.save(npy, embeddings)
                    z.writestr(EMBEDDINGS_NAME, npy.getvalue())
            z.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
    elif kind == "documents":
        owner = dataset.get("owner_user_id")
        docs = models.list_documents(owner) if owner is not None else []
        files = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for doc in docs:
                stored = _stored_path(owner, doc)
                if stored and stored.exists():
                    arc = f"files/{doc['filename']}"
                    z.write(stored, arc)
                    files.append(
                        {
                            "name": doc["filename"],
                            "tags": doc.get("tags", ""),
                            "num_chunks": doc.get("num_chunks", 0),
                            "arcname": arc,
                        }
                    )
            manifest = _manifest(dataset, extra={"files": files, "num_files": len(files)})
            z.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
    else:
        raise DatasetBundleError(f"Unsupported dataset kind '{kind}'.")

    filename = f"{dataset.get('slug') or 'dataset'}.rcdataset.zip"
    return filename, buf.getvalue()


def _stored_path(user_id: int, doc: dict[str, Any]) -> Path | None:
    directory = config.UPLOAD_DIR / str(user_id)
    if not directory.exists():
        return None
    matches = sorted(directory.glob(f"{doc['id']}.*"))
    return matches[0] if matches else None


def _index_collection(
    collection: str,
    df: pl.DataFrame,
    embeddings: np.ndarray,
    dataset_id: int,
) -> int:
    coll = _collection_client().get_or_create_collection(
        name=collection, metadata={"hnsw:space": "cosine"}
    )
    rows = df.to_dicts()
    if len(rows) != len(embeddings):
        raise DatasetBundleError(
            f"Embeddings ({len(embeddings)}) do not match chunks ({len(rows)})."
        )
    ids = [str(r.get("chunk_id")) for r in rows]
    texts = [str(r.get("chunk_text") or "") for r in rows]
    metas: list[dict[str, Any]] = []
    for r in rows:
        meta = {f: "" if r.get(f) is None else str(r.get(f)) for f in _META_FIELDS}
        meta["dataset_id"] = str(dataset_id)
        metas.append(meta)

    batch = config.INGEST_BATCH_SIZE
    for start in range(0, len(ids), batch):
        end = min(len(ids), start + batch)
        coll.upsert(
            ids=ids[start:end],
            embeddings=embeddings[start:end].tolist(),
            documents=texts[start:end],
            metadatas=metas[start:end],
        )
    return len(ids)


def import_regulatory_dataset(
    conn: sqlite3.Connection,
    *,
    filename: str,
    data: bytes,
    embedder: Any = None,
) -> dict[str, Any]:
    """Validate + import a regulatory bundle; returns the new dataset row."""
    if not data:
        raise DatasetBundleError("Uploaded bundle is empty.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DatasetBundleError("Bundle is not a valid zip archive.") from exc

    with zf:
        names = set(zf.namelist())
        if MANIFEST_NAME not in names or CHUNKS_NAME not in names:
            raise DatasetBundleError("Bundle must contain manifest.json and chunks.parquet.")
        manifest = json.loads(zf.read(MANIFEST_NAME))
        if manifest.get("type") != "regulatory":
            raise DatasetBundleError("Only regulatory datasets can be imported.")
        parquet_bytes = zf.read(CHUNKS_NAME)
        emb_bytes = zf.read(EMBEDDINGS_NAME) if EMBEDDINGS_NAME in names else None

    try:
        df = pl.read_parquet(io.BytesIO(parquet_bytes))
    except Exception as exc:
        raise DatasetBundleError(f"Could not read chunks.parquet: {exc}") from exc
    if "chunk_id" not in df.columns or "chunk_text" not in df.columns:
        raise DatasetBundleError("chunks.parquet is missing chunk_id/chunk_text.")

    name = str(manifest.get("name") or Path(filename).stem)
    slug = registry.unique_slug(conn, str(manifest.get("slug") or name))
    collection = f"ds_{slug.replace('-', '_')}"
    target_dir = config.DATASETS_DIR / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = target_dir / "chunks.parquet"
    chunks_path.write_bytes(parquet_bytes)

    dataset_id = models.create_dataset(
        conn,
        owner_user_id=None,
        name=name,
        slug=slug,
        kind="regulatory",
        source="import",
        description=str(manifest.get("description") or ""),
        status="processing",
        meta={"collection": collection, "chunks_path": str(chunks_path)},
    )

    try:
        if emb_bytes is not None:
            embeddings = np.load(io.BytesIO(emb_bytes))
        else:
            texts = [str(t or "") for t in df["chunk_text"].to_list()]
            if embedder is None:
                from src.ingestion.openrouter_embedder import get_openrouter_embedder

                embedder = get_openrouter_embedder()
            embeddings = np.asarray(embedder.encode(texts), dtype="float32")

        if len(embeddings) != df.height:
            raise DatasetBundleError(
                f"Embeddings ({len(embeddings)}) do not match chunks ({df.height})."
            )
        _index_collection(collection, df, embeddings, dataset_id)
    except Exception:
        models.delete_dataset(conn, dataset_id)
        try:
            chunks_path.unlink()
        except OSError:
            pass
        raise

    models.update_dataset(conn, dataset_id, status="ready")
    result = models.get_dataset(conn, dataset_id)
    assert result is not None
    return result
