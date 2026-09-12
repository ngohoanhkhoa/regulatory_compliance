"""Hybrid retrieval: vector + BM25 → reciprocal rank fusion → cross-encoder rerank (§5.4).

Pipeline per query::

    question
      ├── embed (live, OpenRouter) → VectorStore.query → vector hits
      └── tokenize            → KeywordIndex.query → bm25 hits
                fused by reciprocal rank fusion (RRF)
                  → cross-encoder rerank (top RERANK_CANDIDATE_K → top DEFAULT_TOP_K)
                    → RerankedHit[] ready for the generation step

RRF is rank-based (not score-based), so it cleanly merges the two heterogeneous
score scales. The fused pool is capped at `RERANK_CANDIDATE_K` before the
reranker (§5.2), then trimmed to `DEFAULT_TOP_K` (§5.4).

Both sub-retrievers already apply the same metadata pre-filter (default
`status = "In Force"`, §5.4); we re-apply nothing here to avoid drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src import config

RRF_K = 60  # standard reciprocal rank fusion constant


@dataclass
class FusedCandidate:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: float  # fused RRF score (higher = better)
    sources: list[str]  # which retrievers surfaced it: "vector" and/or "bm25"


class QuestionEmbedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class _OpenRouterQuestionEmbedder:
    def __init__(self) -> None:
        from src.ingestion.openrouter_embedder import get_openrouter_embedder

        self._client = get_openrouter_embedder()

    def embed(self, text: str) -> list[float]:
        arr = self._client.encode([text])
        return arr[0].tolist()


def get_question_embedder() -> QuestionEmbedder:
    return _OpenRouterQuestionEmbedder()


def reciprocal_rank_fuse(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    k: int = RRF_K,
) -> list[FusedCandidate]:
    """Fuse multiple ranked candidate lists by reciprocal rank fusion.

    Each input list must already be ordered best→worst and elements must carry
    `chunk_id`, `text`, `metadata`. Identical chunk_ids across lists accumulate
    RRF score (a chunk retrieved by both modalities outranks one from a single).
    """
    scores: dict[str, float] = {}
    meta: dict[str, dict[str, Any]] = {}
    text: dict[str, str] = {}
    src: dict[str, set[str]] = {}

    for list_idx, ranked in enumerate(ranked_lists):
        source_name = ranked[0].get("__source", str(list_idx)) if ranked else str(list_idx)
        for rank, hit in enumerate(ranked):
            cid = str(hit.get("chunk_id"))
            if cid not in meta:
                meta[cid] = dict(hit.get("metadata") or {})
                text[cid] = str(hit.get("text") or "")
                src[cid] = set()
            src[cid].add(source_name)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    fused = [
        FusedCandidate(
            chunk_id=cid,
            text=text[cid],
            metadata=meta[cid],
            score=scores[cid],
            sources=sorted(src[cid]),
        )
        for cid in scores
    ]
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


def _vec_to_dict(hit: Any, source: str) -> dict[str, Any]:
    """Normalise a VectorHit/KeywordHit/RerankedHit-like obj into a plain dict."""
    if hasattr(hit, "as_dict"):
        d = hit.as_dict()
    elif isinstance(hit, dict):
        d = dict(hit)
    else:
        raise TypeError(f"unsupported hit type: {type(hit)}")
    d["__source"] = source
    return d


@dataclass
class HybridResult:
    hits: list  # list[RerankedHit] from the reranker
    candidates: list[FusedCandidate]  # pre-rerank fused pool (for auditing)


def fuse_and_rerank(
    question: str,
    ranked_lists: list[list[dict[str, Any]]],
    *,
    reranker: Any = None,
    n_candidates: int = config.RERANK_CANDIDATE_K,
    top_k: int = config.DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """RRF-fuse any number of ranked hit lists, then rerank to top-k dicts."""
    from src.retrieval import reranker as rr

    fused = reciprocal_rank_fuse(ranked_lists)
    fused_capped = fused[:n_candidates]
    candidate_dicts = [
        {
            "chunk_id": c.chunk_id,
            "text": c.text,
            "metadata": c.metadata,
            "score": c.score,
        }
        for c in fused_capped
    ]
    ranked = rr.rerank(question, candidate_dicts, reranker=reranker, top_k=top_k)
    return [h.as_dict() for h in ranked]


def retrieve(
    question: str,
    *,
    question_embedder: QuestionEmbedder | None = None,
    vector_store: Any = None,
    keyword_index: Any = None,
    reranker: Any = None,
    n_candidates: int = config.RERANK_CANDIDATE_K,
    top_k: int = config.DEFAULT_TOP_K,
    filters: dict[str, Any] | None = None,
    include_repealed: bool = False,
) -> list[dict[str, Any]]:
    """End-to-end hybrid retrieval → rerank → top-k dicts.

    Returns a list of plain dicts (not dataclasses) so it serialises straight
    into the `/query` response schema (§8). Each dict has:
    chunk_id, score (fused), rerank_score, text, metadata.
    """
    if question_embedder is None:
        question_embedder = get_question_embedder()
    if vector_store is None:
        from src.retrieval.vector_store import VectorStore

        vector_store = VectorStore()
    if keyword_index is None:
        from src.retrieval.keyword_index import KeywordIndex

        keyword_index = KeywordIndex()

    q_emb = question_embedder.embed(question)
    vec_hits = vector_store.query(
        q_emb,
        n_results=n_candidates,
        filters=filters,
        include_repealed=include_repealed,
    )
    kw_hits = keyword_index.query(
        question,
        n_results=n_candidates,
        filters=filters,
        include_repealed=include_repealed,
    )

    return fuse_and_rerank(
        question,
        [
            [_vec_to_dict(h, "vector") for h in vec_hits],
            [_vec_to_dict(h, "bm25") for h in kw_hits],
        ],
        reranker=reranker,
        n_candidates=n_candidates,
        top_k=top_k,
    )
