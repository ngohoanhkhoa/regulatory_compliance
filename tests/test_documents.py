"""Tests for the personal document library (upload, list, delete, search).

Embedding and the vector store are faked so tests never hit the network.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.documents.store import DocHit


class _FakeEmbedder:
    def encode(self, texts, **kw):
        return np.ones((len(texts), 4), dtype=float)


class _FakeStore:
    def __init__(self):
        self.upserted: dict[str, dict] = {}
        self.deleted: list[tuple[int, int]] = []

    def upsert(self, *, ids, embeddings, documents, metadatas):
        for i, _id in enumerate(ids):
            self.upserted[_id] = {"text": documents[i], "meta": metadatas[i]}

    def delete_document(self, user_id, document_id):
        self.deleted.append((user_id, document_id))

    def query(self, embedding, user_id, *, n_results=5):
        return [
            DocHit(
                chunk_id="userdoc-1#0000",
                score=0.9,
                text="personal data obligations",
                metadata={
                    "user_id": user_id,
                    "document_id": 1,
                    "filename": "notes.txt",
                    "chunk_index": 0,
                },
            )
        ]


@pytest.fixture()
def fake_store(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr("src.documents.service.UserDocsStore", lambda *a, **k: store)
    monkeypatch.setattr(
        "src.documents.service.get_openrouter_embedder", lambda *a, **k: _FakeEmbedder()
    )
    return store


@pytest.fixture()
def client(tmp_path, monkeypatch, fake_store):
    from src import config
    from src.auth import models

    db = tmp_path / "test.db"
    monkeypatch.setattr(config, "METADATA_DB_PATH", db)
    monkeypatch.setattr(models, "DB_PATH", db)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    from src.api import main as main_mod

    return TestClient(main_mod.app)


def _login(client, username, password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})
    return client.post(
        "/auth/login", data={"username": username, "password": password}
    ).json()["access_token"]


@pytest.fixture()
def user_token(client):
    return _login(client, "user1")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token, content=b"hello world\n\n" * 40, name="notes.txt"):
    return client.post(
        "/api/documents",
        headers=auth(token),
        files={"file": (name, content, "text/plain")},
    )


# --- auth ------------------------------------------------------------------- #

def test_documents_require_auth(client):
    assert client.get("/api/documents").status_code == 401


# --- upload ----------------------------------------------------------------- #

def test_upload_text_document(client, user_token, fake_store):
    r = _upload(client, user_token)
    assert r.status_code == 201
    doc = r.json()
    assert doc["filename"] == "notes.txt"
    assert doc["status"] == "ready"
    assert doc["num_chunks"] >= 1
    assert fake_store.upserted  # chunks were embedded + stored


def test_upload_unsupported_type(client, user_token):
    r = client.post(
        "/api/documents",
        headers=auth(user_token),
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_upload_empty_file(client, user_token):
    r = _upload(client, user_token, content=b"")
    assert r.status_code == 400


def test_upload_blank_text(client, user_token):
    r = _upload(client, user_token, content=b"   \n\n   ")
    assert r.status_code == 400


# --- list / delete ---------------------------------------------------------- #

def test_list_and_delete_document(client, user_token, fake_store):
    doc_id = _upload(client, user_token).json()["id"]
    listed = client.get("/api/documents", headers=auth(user_token)).json()
    assert [d["id"] for d in listed] == [doc_id]

    deleted = client.delete(f"/api/documents/{doc_id}", headers=auth(user_token))
    assert deleted.status_code == 200
    assert client.get("/api/documents", headers=auth(user_token)).json() == []
    assert fake_store.deleted == [(1, doc_id)]


def test_delete_missing_document_404(client, user_token):
    assert client.delete("/api/documents/999", headers=auth(user_token)).status_code == 404


def test_documents_are_private(client, user_token):
    _upload(client, user_token)
    other = _login(client, "user2")
    assert client.get("/api/documents", headers=auth(other)).json() == []


# --- search ----------------------------------------------------------------- #

def test_search_returns_own_document_chunks(client, user_token):
    r = client.post(
        "/api/documents/search",
        headers=auth(user_token),
        json={"query": "data protection", "top_k": 3},
    )
    assert r.status_code == 200
    hits = r.json()
    assert hits[0]["filename"] == "notes.txt"
    assert hits[0]["document_id"] == 1
