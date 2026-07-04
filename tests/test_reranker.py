import pytest

from src.retrieval import reranker as rr


class FakeReranker:
    def __init__(self, scores):
        self._scores = scores
        self.calls = 0

    def score(self, question, candidates):
        self.calls += 1
        return list(self._scores)


def test_rerank_empty():
    assert rr.rerank("q", []) == []


def test_rerank_orders_by_reranker_score_desc():
    hits = [
        {"chunk_id": "a", "text": "x", "metadata": {}, "score": 0.9},
        {"chunk_id": "b", "text": "y", "metadata": {}, "score": 0.5},
        {"chunk_id": "c", "text": "z", "metadata": {}, "score": 0.1},
    ]
    out = rr.rerank("q", hits, reranker=FakeReranker([0.1, 0.8, 0.5]), top_k=2)
    assert [h.chunk_id for h in out] == ["b", "c"]
    assert out[0].rerank_score == 0.8
    assert out[0].score == 0.5  # original fused score preserved for audit
    assert out[0].text == "y"
    assert out[0].metadata == {}


def test_rerank_top_k_caps():
    hits = [{"chunk_id": str(i), "text": str(i), "metadata": {}, "score": 1} for i in range(5)]
    scores = [5 - i for i in range(5)]
    out = rr.rerank("q", hits, reranker=FakeReranker(scores), top_k=3)
    assert len(out) == 3
    assert [h.chunk_id for h in out] == ["0", "1", "2"]


def test_rerank_preserves_metadata_and_text():
    hits = [{"chunk_id": "x", "text": "T", "metadata": {"celex": "Z"}, "score": 1}]
    out = rr.rerank("q", hits, reranker=FakeReranker([0.5]), top_k=1)
    assert out[0].text == "T"
    assert out[0].metadata == {"celex": "Z"}
    assert out[0].rerank_score == 0.5


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
