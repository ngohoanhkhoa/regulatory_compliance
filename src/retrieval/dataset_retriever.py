"""Multi-dataset hybrid retrieval.

Given a set of dataset ids, queries each dataset's vector store (and BM25 index
for regulatory datasets), fuses every ranked list with reciprocal rank fusion,
and reranks the combined pool. Chunk metadata is annotated with the owning
dataset so prompts and citations can attribute sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src import config
from src.auth import models
from src.datasets import registry

_keyword_cache: dict[str, Any] = {}


def _keyword_index(path: Path):
    key = str(path)
    if key not in _keyword_cache:
        from src.retrieval.keyword_index import KeywordIndex

        _keyword_cache[key] = KeywordIndex(path)
    return _keyword_cache[key]


def _annotate(meta: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    out = dict(meta)
    out["dataset_id"] = str(dataset["id"])
    out["dataset_name"] = dataset.get("name", "")
    out["dataset_kind"] = dataset.get("kind", "")
    out["dataset_source"] = dataset.get("source", "")
    if not out.get("item_ref"):
        out["item_ref"] = out.get("celex") or out.get("filename") or ""
    return out


def _ranked_lists_for_dataset(
    dataset: dict[str, Any],
    question: str,
    question_embedding: list[float],
    *,
    n_candidates: int,
    filters: dict[str, Any] | None,
    include_repealed: bool,
) -> list[list[dict[str, Any]]]:
    lists: list[list[dict[str, Any]]] = []
    collection = registry.collection_of(dataset)
    kind = dataset.get("kind")

    if collection:
        from src.retrieval.vector_store import VectorStore

        try:
            store = VectorStore(collection_name=collection)
        except FileNotFoundError:
            store = None
        if store is not None:
            if kind == "documents":
                owner = dataset.get("owner_user_id")
                hits = store.query(
                    question_embedding,
                    n_results=n_candidates,
                    filters={"user_id": int(owner)} if owner is not None else None,
                    include_repealed=True,
                )
            else:
                hits = store.query(
                    question_embedding,
                    n_results=n_candidates,
                    filters=filters,
                    include_repealed=include_repealed,
                )
            lists.append(
                [
                    {
                        "chunk_id": h.chunk_id,
                        "text": h.text,
                        "metadata": _annotate(h.metadata, dataset),
                        "__source": "vector",
                    }
                    for h in hits
                ]
            )

    path = registry.chunks_path_of(dataset)
    if kind == "regulatory" and path and path.exists():
        try:
            idx = _keyword_index(path)
            kw_hits = idx.query(
                question,
                n_results=n_candidates,
                filters=filters,
                include_repealed=include_repealed,
            )
        except FileNotFoundError:
            kw_hits = []
        if kw_hits:
            lists.append(
                [
                    {
                        "chunk_id": h.chunk_id,
                        "text": h.text,
                        "metadata": _annotate(h.metadata, dataset),
                        "__source": "bm25",
                    }
                    for h in kw_hits
                ]
            )
    return lists


def retrieve(
    question: str,
    dataset_ids: list[int],
    *,
    question_embedder: Any = None,
    reranker: Any = None,
    n_candidates: int = config.RERANK_CANDIDATE_K,
    top_k: int = config.DEFAULT_TOP_K,
    filters: dict[str, Any] | None = None,
    include_repealed: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve across the given datasets and return the top-k reranked chunks."""
    conn = models.get_db()
    try:
        datasets = [models.get_dataset(conn, int(did)) for did in dataset_ids]
    finally:
        conn.close()
    datasets = [d for d in datasets if d]
    if not datasets:
        return []

    if question_embedder is None:
        from src.retrieval.hybrid_retriever import get_question_embedder

        question_embedder = get_question_embedder()
    embedding = question_embedder.embed(question)

    all_lists: list[list[dict[str, Any]]] = []
    for dataset in datasets:
        all_lists.extend(
            _ranked_lists_for_dataset(
                dataset,
                question,
                embedding,
                n_candidates=n_candidates,
                filters=filters,
                include_repealed=include_repealed,
            )
        )
    if not all_lists:
        return []

    from src.retrieval.hybrid_retriever import fuse_and_rerank

    return fuse_and_rerank(
        question,
        all_lists,
        reranker=reranker,
        n_candidates=n_candidates,
        top_k=top_k,
    )
