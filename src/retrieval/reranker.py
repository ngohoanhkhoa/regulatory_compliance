"""Cross-encoder reranker for the merged hybrid candidate set (§5.2, §5.4).

A cross-encoder scores each (question, chunk) pair jointly — far more accurate
than bi-encoder similarity alone, at the cost of one model pass per candidate.
We keep the candidate pool small (default 25, §5.4) and cap it at
`RERANK_CANDIDATE_K` (config) so latency stays within the §10 budget (~15-20s
end-to-end). Runs locally on CPU.

The reranker is behind a `Reranker` Protocol so tests/eval can inject a fake
without loading torch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src import config


class Reranker(Protocol):
    def score(self, question: str, candidates: list[str]) -> list[float]: ...


class _CrossEncoderReranker:
    def __init__(self, model_name: str = config.RERANKER_MODEL) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def score(self, question: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        pairs = [(question, c) for c in candidates]
        # Higher score = more relevant; CrossEncoder.predict already returns
        # the raw logits/scores in the model's native order.
        return [float(x) for x in self._model.predict(pairs)]


def get_reranker(model_name: str = config.RERANKER_MODEL) -> Reranker:
    return _CrossEncoderReranker(model_name)


@dataclass
class RerankedHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any]
    rerank_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
            "rerank_score": self.rerank_score,
        }


def rerank(
    question: str,
    hits: list[dict[str, Any]],
    *,
    reranker: Reranker | None = None,
    top_k: int = config.DEFAULT_TOP_K,
) -> list[RerankedHit]:
    """Re-score a candidate list and return the top-k by reranker score.

    `hits` is the fused candidate list (any remaining hybrid scores are kept
    on the output for auditing but are not used for ordering).
    """
    if not hits:
        return []
    reranker = reranker or get_reranker()
    texts = [h.get("text") or "" for h in hits]
    scores = reranker.score(question, texts)
    ranked = sorted(
        zip(hits, scores), key=lambda hs: hs[1], reverse=True
    )
    out: list[RerankedHit] = []
    for h, rs in ranked[:top_k]:
        out.append(
            RerankedHit(
                chunk_id=str(h.get("chunk_id")),
                score=float(h.get("score") or 0.0),
                text=str(h.get("text") or ""),
                metadata=dict(h.get("metadata") or {}),
                rerank_score=float(rs),
            )
        )
    return out
