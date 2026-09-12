"""Tests for the unified dataset registry, bundles, and dataset routes."""

from __future__ import annotations

import io

import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from src.auth import models
from src.datasets import bundle, registry


class _FakeEmbedder:
    def encode(self, texts, **kw):
        return np.ones((len(texts), 4), dtype="float32")


def _chunks_frame():
    return pl.DataFrame(
        {
            "chunk_id": ["32016R0679#0000", "32016R0679#0001"],
            "celex": ["32016R0679", "32016R0679"],
            "chunk_index": [0, 1],
            "chunk_text": ["Article 1 GDPR scope", "Article 2 GDPR data"],
            "boundary": ["Article 1", "Article 2"],
            "act_name": ["GDPR", "GDPR"],
            "status": ["In Force", "In Force"],
            "date_document": ["2016-04-27", "2016-04-27"],
            "temporal_status": ["", ""],
            "eurovoc": ["", ""],
            "subject_matter": ["", ""],
            "eurlex_link": ["http://e/1", "http://e/1"],
        }
    )


@pytest.fixture()
def env(tmp_path, monkeypatch):
    from src import config

    db = tmp_path / "test.db"
    monkeypatch.setattr(config, "METADATA_DB_PATH", db)
    monkeypatch.setattr(models, "DB_PATH", db)
    monkeypatch.setattr(config, "VECTOR_STORE_DIR", tmp_path / "vs")
    monkeypatch.setattr(config, "DATASETS_DIR", tmp_path / "datasets")
    return tmp_path


@pytest.fixture()
def client(env):
    from src.api import main as main_mod

    with TestClient(main_mod.app) as c:
        yield c


def _login(client, username, password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})
    return client.post(
        "/auth/login", data={"username": username, "password": password}
    ).json()["access_token"]


def _admin_token(client):
    # The default admin is created at startup (admin / 0000).
    return client.post(
        "/auth/login", data={"username": "admin", "password": "0000"}
    ).json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_regulatory(tmp_path, *, slug="test-reg"):
    path = tmp_path / f"{slug}.parquet"
    _chunks_frame().write_parquet(path)
    conn = models.get_db()
    try:
        did = models.create_dataset(
            conn,
            name="Test Regulation Set",
            slug=slug,
            kind="regulatory",
            source="import",
            meta={"collection": f"ds_{slug.replace('-', '_')}", "chunks_path": str(path)},
        )
    finally:
        conn.close()
    return did, path


# --- registry ---------------------------------------------------------------- #

def test_slugify_and_unique_slug(env):
    assert registry.slugify("My Data Set!") == "my-data-set"
    conn = models.get_db()
    try:
        models.create_dataset(
            conn, name="X", slug="dup", kind="regulatory", source="import"
        )
        assert registry.unique_slug(conn, "dup") == "dup-2"
    finally:
        conn.close()


def test_ensure_user_documents_dataset_is_idempotent(env):
    conn = models.get_db()
    try:
        uid = models.create_user(conn, username="u42", hashed_password="x", is_admin=False)
        a = models.ensure_user_documents_dataset(conn, uid)
        b = models.ensure_user_documents_dataset(conn, uid)
        assert a["id"] == b["id"]
        assert a["kind"] == "documents"
        assert a["owner_user_id"] == uid
    finally:
        conn.close()


# --- bundles ----------------------------------------------------------------- #

def test_export_import_roundtrip(env):
    tmp_path = env
    did, _ = _seed_regulatory(tmp_path, slug="round-trip")
    conn = models.get_db()
    try:
        dataset = models.get_dataset(conn, did)
        filename, payload = bundle.export_dataset(dataset, include_embeddings=False)
        assert filename.endswith(".rcdataset.zip")

        imported = bundle.import_regulatory_dataset(
            conn,
            filename=filename,
            data=payload,
            embedder=_FakeEmbedder(),
        )
        assert imported["kind"] == "regulatory"
        assert imported["name"] == "Test Regulation Set"
        assert imported["id"] != did
        stats = registry.dataset_stats(conn, imported)
        assert stats["chunks"] == 2
        assert stats["vectors"] == 2
    finally:
        conn.close()


def test_import_rejects_non_zip(env):
    conn = models.get_db()
    try:
        with pytest.raises(bundle.DatasetBundleError):
            bundle.import_regulatory_dataset(conn, filename="x.zip", data=b"nope")
    finally:
        conn.close()


# --- routes ------------------------------------------------------------------ #

def test_datasets_require_auth(client):
    assert client.get("/api/datasets").status_code == 401


def test_list_datasets_includes_eurlex_and_my_documents(client):
    token = _login(client, "user1")
    data = client.get("/api/datasets", headers=auth(token)).json()
    names = {d["name"]: d for d in data}
    assert "EURLEX Regulatory Texts" in names
    assert "My Documents" in names
    assert names["My Documents"]["kind"] == "documents"
    assert names["EURLEX Regulatory Texts"]["kind"] == "regulatory"


def test_dataset_acts_read_only(client, env):
    token = _admin_token(client)
    did, _ = _seed_regulatory(env)
    r = client.get(f"/api/datasets/{did}/acts?query=gdpr", headers=auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == "32016R0679"
    assert [c["key"] for c in body["columns"]] == [
        "id",
        "title",
        "status",
        "date",
        "chunks",
    ]


def test_dataset_item_content(client, env):
    token = _admin_token(client)
    did, _ = _seed_regulatory(env)
    r = client.get(f"/api/datasets/{did}/items/32016R0679", headers=auth(token))
    assert r.status_code == 200
    item = r.json()
    assert item["id"] == "32016R0679"
    assert item["title"] == "GDPR"
    assert len(item["chunks"]) == 2
    assert item["chunks"][0]["text"] == "Article 1 GDPR scope"


def test_dataset_item_missing_404(client, env):
    token = _admin_token(client)
    did, _ = _seed_regulatory(env)
    r = client.get(f"/api/datasets/{did}/items/NOPE", headers=auth(token))
    assert r.status_code == 404


def test_delete_documents_dataset_rejected(client, env):
    token = _admin_token(client)
    data = client.get("/api/datasets", headers=auth(token)).json()
    docs = next(d for d in data if d["kind"] == "documents")
    r = client.delete(f"/api/datasets/{docs['id']}", headers=auth(token))
    assert r.status_code == 400


def test_import_requires_admin(client, env):
    _admin_token(client)
    user_token = _login(client, "member")
    r = client.post(
        "/api/datasets/import",
        headers=auth(user_token),
        files={"file": ("x.zip", io.BytesIO(b"nope"), "application/zip")},
    )
    assert r.status_code == 403


def test_admin_can_delete_regulatory_dataset(client, env):
    token = _admin_token(client)
    did, _ = _seed_regulatory(env, slug="to-remove")
    r = client.delete(f"/api/datasets/{did}", headers=auth(token))
    assert r.status_code == 200
    conn = models.get_db()
    try:
        assert models.get_dataset(conn, did) is None
    finally:
        conn.close()
