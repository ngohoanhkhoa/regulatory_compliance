import pytest

from src.retrieval.hybrid_retriever import (
    RRF_K,
    reciprocal_rank_fuse,
)


def _hit(cid, rank):
    return {"chunk_id": cid, "text": f"t{cid}", "metadata": {"celex": cid}}


def test_rrf_empty_returns_empty():
    assert reciprocal_rank_fuse([]) == []
    assert reciprocal_rank_fuse([[], []]) == []


def test_rrf_single_list_preserves_order():
    lst = [{"__source": "v", "chunk_id": "a", "text": "x", "metadata": {}},
           {"__source": "v", "chunk_id": "b", "text": "x", "metadata": {}}]
    out = reciprocal_rank_fuse([lst])
    assert [c.chunk_id for c in out] == ["a", "b"]
    assert out[0].score > out[1].score


def test_rrf_chunk_in_both_lists_outranks_single_source():
    vec = [{"__source": "vector", "chunk_id": "a", "text": "x", "metadata": {}},
           {"__source": "vector", "chunk_id": "b", "text": "x", "metadata": {}}]
    bm = [{"__source": "bm25", "chunk_id": "b", "text": "x", "metadata": {}},
          {"__source": "bm25", "chunk_id": "c", "text": "x", "metadata": {}}]
    out = reciprocal_rank_fuse([vec, bm])
    # 'b' is in both -> sum of two RRF contributions -> top
    assert out[0].chunk_id == "b"
    assert set(out[0].sources) == {"bm25", "vector"}
    assert "vector" in out[1].sources or "bm25" in out[1].sources


def test_rrf_scores_finite_and_decreasing():
    lst = [{"__source": "v", "chunk_id": str(i), "text": "x", "metadata": {}} for i in range(5)]
    out = reciprocal_rank_fuse([lst])
    for c in out:
        assert c.score == pytest.approx(1.0 / (RRF_K + int(c.chunk_id) + 1))
    assert [c.score for c in out] == sorted((c.score for c in out), reverse=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
