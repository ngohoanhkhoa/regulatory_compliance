import pytest

from src.retrieval import hybrid_retriever as hr


class FakeQEmbedder:
    def embed(self, text):
        return [0.1, 0.2]


class FakeVecStore:
    def __init__(self, hits):
        self._hits = hits

    def query(self, emb, *, n_results=10, filters=None, include_repealed=False):
        return self._hits


class FakeKWIndex:
    def __init__(self, hits):
        self._hits = hits

    def query(self, q, *, n_results=10, filters=None, include_repealed=False):
        return self._hits


class FakeReranker:
    def __init__(self, scores=None):
        self._scores = scores

    def score(self, question, candidates):
        if self._scores is not None:
            return list(self._scores)
        # default: reverse the input order so test ordering is deterministic
        return list(range(len(candidates)))[::-1]


def _vhdict(cid):
    from src.retrieval.vector_store import VectorHit
    return VectorHit(chunk_id=cid, score=0.5, text=f"t{cid}", metadata={"celex": cid})


def test_retrieve_end_to_end_with_fakes():
    vec_hits = [_vhdict("a"), _vhdict("b"), _vhdict("c")]
    from src.retrieval.keyword_index import KeywordHit
    kw_hits = [
        KeywordHit(chunk_id="b", score=3.0, text="tb", metadata={"celex": "b"}),
        KeywordHit(chunk_id="d", score=2.0, text="td", metadata={"celex": "d"}),
    ]
    reranker = FakeReranker(scores=[0.9, 0.5, 0.7, 0.1])

    out = hr.retrieve(
        "question about GDPR",
        question_embedder=FakeQEmbedder(),
        vector_store=FakeVecStore(vec_hits),
        keyword_index=FakeKWIndex(kw_hits),
        reranker=reranker,
        n_candidates=10,
        top_k=3,
    )
    assert isinstance(out, list)
    assert len(out) <= 3
    # all entries are plain serialisable dicts
    assert all(isinstance(h, dict) for h in out)
    for h in out:
        assert {"chunk_id", "score", "text", "metadata", "rerank_score"} <= set(h.keys())


def test_retrieve_empty_question():
    out = hr.retrieve(
        "",
        question_embedder=FakeQEmbedder(),
        vector_store=FakeVecStore([]),
        keyword_index=FakeKWIndex([]),
        reranker=FakeReranker(),
    )
    assert out == []


def test_retrieve_passes_filters_and_include_repealed():
    class SpyVecStore:
        def __init__(self):
            self.calls = 0

        def query(self, emb, *, n_results, filters, include_repealed):
            # record the actual call args
            self.calls += 1
            self.last_filters = filters
            self.last_include_repealed = include_repealed
            return []

    class SpyKWIndex:
        def __init__(self):
            self.calls = 0

        def query(self, q, *, n_results, filters, include_repealed):
            self.calls += 1
            self.last_filters = filters
            self.last_include_repealed = include_repealed
            return []

    vs = SpyVecStore()
    ki = SpyKWIndex()
    hr.retrieve(
        "q", question_embedder=FakeQEmbedder(),
        vector_store=vs, keyword_index=ki, reranker=FakeReranker(),
        filters={"celex": "X"}, include_repealed=True,
    )
    assert vs.last_filters == {"celex": "X"}
    assert vs.last_include_repealed is True
    assert ki.last_filters == {"celex": "X"}
    assert ki.last_include_repealed is True


# --- real-corpus smoke (skipped unless vector store + parquet exist) ---


def _has_real_store():
    from src import config
    return (
        config.VECTOR_STORE_DIR.exists()
        and config.PROCESSED_CHUNKS_PATH.exists()
    )


@pytest.mark.skipif(not _has_real_store(), reason="vector store / chunks not built")
def test_real_hybrid_retrieval_smoke():
    """Smoke: load real VectorStore + KeywordIndex + cross-encoder reranker.

    This actually loads the BGE reranker (~400MB download first time). Keep it
    marked skip-on-missing to avoid network/torch cost in normal CI runs.
    """
    out = hr.retrieve("data protection of natural persons personal data GDPR")
    assert out, "expected at least one hit"
    ids = [h["chunk_id"] for h in out]
    assert len(ids) == len(set(ids))  # no duplicates
    for h in out:
        assert h["text"]
        assert "celex" in h["metadata"]
