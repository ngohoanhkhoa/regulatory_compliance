"""Personal document library service: extract → chunk → embed → store."""

from __future__ import annotations

import sqlite3
from typing import Any

from src import config
from src.auth import models
from src.documents import chunker, extract
from src.documents.store import UserDocsStore
from src.ingestion.openrouter_embedder import get_openrouter_embedder


def _upload_path(user_id: int, document_id: int, ext: str):
    directory = config.UPLOAD_DIR / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{document_id}{ext}"


def create_document(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    filename: str,
    content_type: str,
    data: bytes,
    dataset_id: int | None = None,
    tags: str = "",
    embedder: Any = None,
    store: Any = None,
) -> dict[str, Any]:
    """Ingest an uploaded file and return its persisted metadata row.

    Raises ``UnsupportedDocument`` / ``ValueError`` for bad input, or re-raises
    embed/store failures after marking the row as errored.
    """
    ext = extract.extension_of(filename)
    if ext not in extract.SUPPORTED_EXTENSIONS:
        raise extract.UnsupportedDocument(
            f"Unsupported file type '{ext or filename}'."
        )

    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"File too large (max {config.MAX_UPLOAD_MB} MB).")
    if not data:
        raise ValueError("Uploaded file is empty.")

    text = extract.extract_text(filename, data)
    if not text.strip():
        raise ValueError("No extractable text found in the document.")

    if dataset_id is None:
        dataset_id = models.ensure_user_documents_dataset(conn, user_id)["id"]

    doc_id = models.create_document(
        conn,
        user_id=user_id,
        dataset_id=dataset_id,
        filename=filename or "upload",
        content_type=content_type or "",
        size_bytes=len(data),
        tags=tags or "",
        status="processing",
    )
    _upload_path(user_id, doc_id, ext).write_bytes(data)

    try:
        chunks = chunker.chunk_text(text, f"userdoc-{doc_id}")
        if not chunks:
            raise ValueError("Document produced no chunks.")
        embedder = embedder if embedder is not None else get_openrouter_embedder()
        vectors = embedder.encode([c["chunk_text"] for c in chunks])
        store = store if store is not None else UserDocsStore()
        store.upsert(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=vectors.tolist(),
            documents=[c["chunk_text"] for c in chunks],
            metadatas=[
                {
                    "user_id": int(user_id),
                    "dataset_id": int(dataset_id),
                    "document_id": int(doc_id),
                    "filename": filename or "upload",
                    "tags": tags or "",
                    "chunk_index": int(c["chunk_index"]),
                }
                for c in chunks
            ],
        )
    except Exception as exc:
        models.finish_document(conn, doc_id, num_chunks=0, status="error", error=str(exc)[:500])
        raise

    models.finish_document(conn, doc_id, num_chunks=len(chunks), status="ready")
    result = models.get_document(conn, user_id, doc_id)
    assert result is not None
    return result


def search_documents(
    user_id: int,
    query: str,
    *,
    top_k: int = 5,
    embedder: Any = None,
    store: Any = None,
) -> list[dict[str, Any]]:
    question = (query or "").strip()
    if not question:
        return []
    embedder = embedder if embedder is not None else get_openrouter_embedder()
    vector = embedder.encode([question])[0].tolist()
    store = store if store is not None else UserDocsStore()
    return [h.as_dict() for h in store.query(vector, user_id, n_results=top_k)]


def delete_document(
    conn: sqlite3.Connection,
    user_id: int,
    document_id: int,
    *,
    store: Any = None,
) -> bool:
    if models.get_document(conn, user_id, document_id) is None:
        return False
    (store if store is not None else UserDocsStore()).delete_document(
        user_id, document_id
    )
    directory = config.UPLOAD_DIR / str(user_id)
    if directory.exists():
        for f in directory.glob(f"{document_id}.*"):
            try:
                f.unlink()
            except OSError:
                pass
    models.delete_document_row(conn, user_id, document_id)
    return True
