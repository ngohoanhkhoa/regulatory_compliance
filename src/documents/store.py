"""Chroma wrapper for the per-user document collection.

Kept separate from the regulatory ``eurlex_chunks`` collection so personal
documents never mix into regulatory retrieval. Every chunk carries ``user_id``
metadata, and queries are always filtered by the current user.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src import config


@dataclass
class DocHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }


class UserDocsStore:
    def __init__(self, persist_dir: Path = config.VECTOR_STORE_DIR) -> None:
        import chromadb

        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._coll = self._client.get_or_create_collection(
            name=config.USER_DOCS_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return int(self._coll.count())

    def upsert(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._coll.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def delete_document(self, user_id: int, document_id: int) -> None:
        self._coll.delete(
            where={
                "$and": [
                    {"user_id": int(user_id)},
                    {"document_id": int(document_id)},
                ]
            }
        )

    def query(
        self, embedding: list[float], user_id: int, *, n_results: int = 5
    ) -> list[DocHit]:
        res = self._coll.query(
            query_embeddings=[embedding],
            n_results=max(1, n_results),
            where={"user_id": int(user_id)},
            include=["documents", "metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        hits: list[DocHit] = []
        for i, _id in enumerate(ids):
            dist = float(dists[i]) if i < len(dists) else 1.0
            hits.append(
                DocHit(
                    chunk_id=str(_id),
                    score=max(0.0, 1.0 - dist),
                    text=str(docs[i]) if i < len(docs) else "",
                    metadata=dict(metas[i]) if i < len(metas) else {},
                )
            )
        return hits
