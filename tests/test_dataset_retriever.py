"""Tests for multi-dataset hybrid retrieval fusion."""

from __future__ import annotations

import pytest

from src.auth import models
from src.retrieval import dataset_retriever
from src.retrieval.vector_store import VectorHit


class FakeEmbedder:
    def embed(self, text):
        return [0.1, 0.2]


class FakeReranker:
    def score(self, question, candidates):
        return list(range(len(candidates)))[::-1]


class FakeVectorStore:
    def __init__(self, persist_dir=None, *, collection_name="eurlex_chunks"):
        self.collection_name = collection_name

    def query(self, embedding, *, n_results=10, filters=None, include_repealed=False):
        if self.collection_name == "docs":
            return [
                VectorHit(
                    chunk_id="userdoc-1#0000",
                    score=0.8,
                    text="contract clause",
                    metadata={
                        "user_id": 1,
                        "dataset_id": "2",
                        "filename": "contract.pdf",
                    },
                )
            ]
        return [
            VectorHit(
                chunk_id="32016R0679#0000",
                score=0.9,
                text="gdpr article",
                metadata={"celex": "32016R0679", "act_name": "GDPR"},
            )
        ]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    from src import config

    db = tmp_path / "test.db"
    monkeypatch.setattr(config, "METADATA_DB_PATH", db)
    monkeypatch.setattr(models, "DB_PATH", db)
    conn = models.get_db()
    try:
        uid = models.create_user(conn, username="u1", hashed_password="x", is_admin=False)
        reg = models.create_dataset(
            conn,
            name="REG",
            slug="reg",
            kind="regulatory",
            source="import",
            meta={"collection": "reg", "chunks_path": str(tmp_path / "nope.parquet")},
        )
        docs = models.create_dataset(
            conn,
            owner_user_id=uid,
            name="My Documents",
            slug="docs-1",
            kind="documents",
            source="upload",
            meta={"collection": "docs"},
        )
    finally:
        conn.close()
    return {"reg": reg, "docs": docs, "uid": uid}


def test_retrieve_fuses_multiple_datasets(env, monkeypatch):
    monkeypatch.setattr("src.retrieval.vector_store.VectorStore", FakeVectorStore)

    hits = dataset_retriever.retrieve(
        "question",
        [env["reg"], env["docs"]],
        question_embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        top_k=5,
    )
    assert hits
    names = {h["metadata"].get("dataset_name") for h in hits}
    assert "REG" in names
    assert "My Documents" in names

    doc_hit = next(h for h in hits if h["metadata"]["dataset_kind"] == "documents")
    assert doc_hit["metadata"]["item_ref"] == "contract.pdf"


def test_retrieve_unknown_dataset_returns_empty(env, monkeypatch):
    monkeypatch.setattr("src.retrieval.vector_store.VectorStore", FakeVectorStore)
    assert dataset_retriever.retrieve("q", [9999], question_embedder=FakeEmbedder()) == []
