import numpy as np
import polars as pl
import pytest

from src.ingestion import embed_and_index as eai


@pytest.fixture()
def tiny_parquet(tmp_path):
    df = pl.DataFrame(
        {
            "chunk_id": [f"C#000{i}" for i in range(5)],
            "celex": ["C"] * 5,
            "chunk_index": list(range(5)),
            "chunk_text": [f"Article {i} subject matter scope of regulation." for i in range(5)],
            "char_offset_start": list(range(0, 5)),
            "char_offset_end": list(range(10, 15)),
            "boundary": ["Article 1", "Article 2", "Article 3", "Article 4", "Article 5"],
            "status": ["In Force"] * 4 + ["Not in Force"],
            "date_document": ["2019-01-01"] * 5,
            "temporal_status": [""] * 5,
            "eurovoc": ["x"] * 5,
            "subject_matter": ["y"] * 5,
            "eurlex_link": ["http://x"] * 5,
            "act_name": ["Act"] * 5,
        }
    )
    p = tmp_path / "chunks.parquet"
    df.write_parquet(p)
    return p


class FakeEmbedder:
    def __init__(self, dim=4):
        self.dim = dim

    def encode(self, texts, **kwargs):
        # deterministic pseudo-embedding, all positive
        n = len(texts)
        return np.ones((n, self.dim), dtype="float32")


class FakeStore:
    def __init__(self, persist_dir=None):
        self.saved = None

    def get_or_create_collection(self, name=eai.COLLECTION_NAME):
        class Coll:
            def __init__(self):
                self.upserts = []

            def upsert(self, ids, embeddings, documents, metadatas):
                self.upserts.append(
                    {"ids": ids, "embeddings": embeddings,
                     "documents": documents, "metadatas": metadatas}
                )

        self._coll = Coll()
        return self._coll


def test_embed_index_runs_with_fakes(tiny_parquet):
    store = FakeStore()
    stats = eai.embed_index(
        chunks_path=tiny_parquet,
        limit=None,
        batch_size=3,
        embedder=FakeEmbedder(),
        vector_store=store,
    )
    assert stats.chunks_seen == 5
    assert stats.chunks_upserted == 5
    assert stats.batches == 2  # 3 + 2


def test_metadata_normalisation_strips_none(tiny_parquet, monkeypatch):
    store = FakeStore()
    # inject a None into a metadata field
    df = pl.read_parquet(tiny_parquet).with_columns(pl.lit(None).alias("status"))
    p = tiny_parquet.parent / "with_none.parquet"
    df.write_parquet(p)
    stats = eai.embed_index(
        chunks_path=p, embedder=FakeEmbedder(), vector_store=store
    )
    assert stats.chunks_upserted == 5
    metas = [m for up in store._coll.upserts for m in up["metadatas"]]
    assert all(m["status"] == "" for m in metas)  # None -> ""
