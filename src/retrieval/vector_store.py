"""ChromaDB query wrapper for the `eurlex_chunks` collection (§5.4).

Encapsulates:
- opening the persisted collection,
- metadata pre-filtering (default `Status = "In Force"`, §5.4),
- returning results in a stable, typed shape the rest of the pipeline uses.

Chroma's `where` filter is built here so callers don't assemble filter dicts ad
hoc. `None` values (our M2 normalise-to-empty-string policy) are mapped to
`{"$ne": "In Force"}` semantics via a presence check so "Not in Force" /
null / empty all count as not-in-force, matching the spec intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src import config

DEFAULT_N_RESULTS = 25  # candidate pool passed to the reranker (§5.4)


@dataclass
class VectorHit:
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


def _build_where(filters: dict[str, Any] | None, include_repealed: bool) -> dict[str, Any] | None:
    """Build a Chroma ``where`` clause.

    Chroma (1.x) requires exactly one top-level operator, so multiple
    conditions are combined with ``$and``. ``filters`` values may already be
    operator expressions (e.g. ``{"celex": {"$in": [...]}}``). The default
    ``status = "In Force"`` is applied unless ``include_repealed`` is set (in
    which case a caller-supplied status filter is honoured).
    """
    conditions: list[dict[str, Any]] = []
    status_value: Any = None
    if filters:
        for key, value in filters.items():
            if value is None:
                continue
            if key == "status":
                status_value = value
                continue
            conditions.append({key: value})

    if not include_repealed:
        conditions.append({"status": "In Force"})
    elif status_value is not None:
        conditions.append({"status": status_value})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


class VectorStore:
    def __init__(
        self,
        persist_dir: Path = config.VECTOR_STORE_DIR,
        *,
        collection_name: str = "eurlex_chunks",
    ) -> None:
        import chromadb

        if not persist_dir.exists():
            raise FileNotFoundError(
                f"vector store not found at {persist_dir}. Run M2 embedding first."
            )
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._coll = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    @property
    def count(self) -> int:
        return int(self._coll.count())

    def query(
        self,
        question_embedding: list[float],
        *,
        n_results: int = DEFAULT_N_RESULTS,
        filters: dict[str, Any] | None = None,
        include_repealed: bool = False,
    ) -> list[VectorHit]:
        where = _build_where(filters, include_repealed)
        res = self._coll.query(
            query_embeddings=[question_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        hits: list[VectorHit] = []
        for i, _id in enumerate(ids):
            dist = float(dists[i]) if i < len(dists) else 1.0
            # cosine distance -> similarity in [0,1]; higher is better.
            score = max(0.0, 1.0 - dist)
            hits.append(
                VectorHit(
                    chunk_id=str(_id),
                    score=score,
                    text=str(docs[i]) if i < len(docs) else "",
                    metadata=dict(metas[i]) if i < len(metas) else {},
                )
            )
        return hits
