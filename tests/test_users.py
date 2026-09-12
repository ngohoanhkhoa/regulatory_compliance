"""Tests for self-service account changes and admin user management."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.auth import models


@pytest.fixture()
def env(tmp_path, monkeypatch):
    from src import config

    db = tmp_path / "test.db"
    monkeypatch.setattr(config, "METADATA_DB_PATH", db)
    monkeypatch.setattr(models, "DB_PATH", db)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "VECTOR_STORE_DIR", tmp_path / "vs")
    return tmp_path


@pytest.fixture()
def client(env):
    from src.api import main as main_mod

    with TestClient(main_mod.app) as c:
        yield c


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client):
    return client.post(
        "/auth/login", data={"username": "admin", "password": "0000"}
    ).json()["access_token"]


def _register_login(client, username, password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})
    return client.post(
        "/auth/login", data={"username": username, "password": password}
    ).json()["access_token"]


def _user_id(client, token, username):
    users = client.get("/api/admin/users", headers=auth(token)).json()
    return next(u["id"] for u in users if u["username"] == username)


# --- self service ------------------------------------------------------------ #

def test_self_update_username(client):
    token = _register_login(client, "alice")
    r = client.put("/auth/me/username", json={"username": "alice2"}, headers=auth(token))
    assert r.status_code == 200
    assert r.json()["username"] == "alice2"
    assert client.get("/auth/me", headers=auth(token)).json()["username"] == "alice2"
    # new name is usable, old is not
    assert (
        client.post(
            "/auth/login", data={"username": "alice2", "password": "password123"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/login", data={"username": "alice", "password": "password123"}
        ).status_code
        == 401
    )


def test_self_username_conflict_case_insensitive(client):
    _register_login(client, "alice")
    bob_token = _register_login(client, "bob")
    r = client.put(
        "/auth/me/username", json={"username": "ALICE"}, headers=auth(bob_token)
    )
    assert r.status_code == 409


def test_self_username_same_case_change_allowed(client):
    token = _register_login(client, "alice")
    r = client.put("/auth/me/username", json={"username": "Alice"}, headers=auth(token))
    assert r.status_code == 200
    assert r.json()["username"] == "Alice"


def test_self_password_change(client):
    token = _register_login(client, "alice")
    wrong = client.put(
        "/auth/me/password",
        json={"current_password": "nope", "new_password": "newpass123"},
        headers=auth(token),
    )
    assert wrong.status_code == 400

    ok = client.put(
        "/auth/me/password",
        json={"current_password": "password123", "new_password": "newpass123"},
        headers=auth(token),
    )
    assert ok.status_code == 200
    assert (
        client.post(
            "/auth/login", data={"username": "alice", "password": "password123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", data={"username": "alice", "password": "newpass123"}
        ).status_code
        == 200
    )


# --- admin ------------------------------------------------------------------- #

def test_admin_users_requires_admin(client):
    user_token = _register_login(client, "user1")
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/admin/users", headers=auth(user_token)).status_code == 403
    assert client.get("/api/admin/users", headers=auth(_admin_token(client))).status_code == 200


def test_admin_create_user(client):
    admin = _admin_token(client)
    r = client.post(
        "/api/admin/users",
        json={"username": "carol", "password": "password123", "is_admin": False},
        headers=auth(admin),
    )
    assert r.status_code == 201
    assert r.json()["username"] == "carol"
    assert r.json()["is_admin"] is False

    dup = client.post(
        "/api/admin/users",
        json={"username": "carol", "password": "password123"},
        headers=auth(admin),
    )
    assert dup.status_code == 409


def test_admin_rename_and_reset_password(client):
    admin = _admin_token(client)
    client.post(
        "/api/admin/users",
        json={"username": "dave", "password": "password123"},
        headers=auth(admin),
    )
    dave_id = _user_id(client, admin, "dave")

    r = client.put(
        f"/api/admin/users/{dave_id}/username",
        json={"username": "dave2"},
        headers=auth(admin),
    )
    assert r.status_code == 200
    assert r.json()["username"] == "dave2"

    pw = client.put(
        f"/api/admin/users/{dave_id}/password",
        json={"new_password": "resetpass1"},
        headers=auth(admin),
    )
    assert pw.status_code == 200
    assert (
        client.post(
            "/auth/login", data={"username": "dave2", "password": "resetpass1"}
        ).status_code
        == 200
    )


def test_admin_grant_and_revoke(client):
    admin = _admin_token(client)
    client.post(
        "/api/admin/users",
        json={"username": "erin", "password": "password123"},
        headers=auth(admin),
    )
    erin_id = _user_id(client, admin, "erin")

    granted = client.put(
        f"/api/admin/users/{erin_id}/admin",
        json={"is_admin": True},
        headers=auth(admin),
    )
    assert granted.status_code == 200
    assert granted.json()["is_admin"] is True

    revoked = client.put(
        f"/api/admin/users/{erin_id}/admin",
        json={"is_admin": False},
        headers=auth(admin),
    )
    assert revoked.status_code == 200
    assert revoked.json()["is_admin"] is False


def test_admin_cannot_demote_or_delete_self(client):
    admin = _admin_token(client)
    admin_id = _user_id(client, admin, "admin")

    demote = client.put(
        f"/api/admin/users/{admin_id}/admin",
        json={"is_admin": False},
        headers=auth(admin),
    )
    assert demote.status_code == 400

    delete = client.delete(f"/api/admin/users/{admin_id}", headers=auth(admin))
    assert delete.status_code == 400


def test_admin_delete_user_hard(client):
    admin = _admin_token(client)
    user_token = _register_login(client, "frank")
    frank_id = _user_id(client, admin, "frank")

    # give frank a topic so we can assert cascade cleanup
    topic = client.post(
        "/api/topics",
        json={"name": "Frank topic", "description": "d"},
        headers=auth(user_token),
    )
    assert topic.status_code == 201

    r = client.delete(f"/api/admin/users/{frank_id}", headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    users = client.get("/api/admin/users", headers=auth(admin)).json()
    assert all(u["username"] != "frank" for u in users)
    assert (
        client.post(
            "/auth/login", data={"username": "frank", "password": "password123"}
        ).status_code
        == 401
    )

    conn = models.get_db()
    try:
        assert models.list_topics(conn, frank_id) == []
        assert models.get_user_by_id(conn, frank_id) is None
    finally:
        conn.close()
