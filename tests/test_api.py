"""Tests for the FastAPI auth + API layer (M5).

Generation is mocked so the suite runs fast and doesn't require the LLM API.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # point the metadata DB to a temp file so test users don't pollute the real DB
    from src import config
    from src.auth import models
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "METADATA_DB_PATH", db_path)
    monkeypatch.setattr(models, "DB_PATH", db_path)
    from src.api import main as main_mod
    return TestClient(main_mod.app)


@pytest.fixture()
def admin_token(client):
    r = client.post("/auth/register", json={"username": "admin", "password": "adminpass123"})
    assert r.status_code == 201
    assert r.json()["is_admin"] is True
    r = client.post("/auth/login", data={"username": "admin", "password": "adminpass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture()
def user_token(client):
    # register admin first so this user is NOT admin
    client.post("/auth/register", json={"username": "admin", "password": "adminpass123"})
    r = client.post("/auth/register", json={"username": "user1", "password": "user1pass123"})
    assert r.status_code == 201
    assert r.json()["is_admin"] is False
    r = client.post("/auth/login", data={"username": "user1", "password": "user1pass123"})
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- health ----------------------------------------------------------------- #

def test_health_status(client):
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] in ("ok", "degraded")
    assert "config" in j
    assert "components" in j


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "docs" in r.json()


def test_openapi_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


# --- auth ------------------------------------------------------------------- #

def test_register_first_user_is_admin(client):
    r = client.post("/auth/register", json={"username": "alpha", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["is_admin"] is True


def test_register_second_user_is_not_admin(client):
    client.post("/auth/register", json={"username": "alpha", "password": "password123"})
    r = client.post("/auth/register", json={"username": "beta", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["is_admin"] is False


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "dupx", "password": "password123"})
    r = client.post("/auth/register", json={"username": "dupx", "password": "password123"})
    assert r.status_code == 409


def test_register_short_password(client):
    r = client.post("/auth/register", json={"username": "shortpw", "password": "short"})
    assert r.status_code == 422  # min_length=8


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "u", "password": "password123"})
    r = client.post("/auth/login", data={"username": "u", "password": "wrongpass99"})
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = client.post("/auth/login", data={"username": "ghost", "password": "whatever"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_user(client, user_token):
    r = client.get("/auth/me", headers=auth_headers(user_token))
    assert r.status_code == 200
    assert r.json()["username"] == "user1"
    assert r.json()["is_admin"] is False


# --- query ------------------------------------------------------------------ #

def test_query_requires_auth(client):
    r = client.post("/query", json={"question": "GDPR?"})
    assert r.status_code == 401


def _mock_orchestrator(monkeypatch, answer="Mock answer about 32016R0679.", grounded=True):
    """Replace orchestrator.answer_question with a deterministic stub."""
    def fake_answer_question(
        question,
        *,
        top_k=7,
        filters=None,
        include_repealed=False,
        session_id=None,
        dataset_ids=None,
        document_ids=None,
    ):
        return {
            "answer": answer,
            "sources": [
                {
                    "celex": "32016R0679",
                    "act_name": "GDPR",
                    "status": "In Force",
                    "link": "http://e/1",
                    "chunk_excerpt": "Article 1 subject matter.",
                }
            ],
            "warnings": ["Dataset frozen at 2019-08-31"],
            "disclaimer": "Not legal advice.",
            "grounded": grounded,
            "ungrounded_celex": [] if grounded else ["31999R9999"],
            "model": "mock-model",
        }

    monkeypatch.setattr("src.api.routes_query.orchestrator.answer_question", fake_answer_question)


def test_query_returns_answer_and_logs(client, admin_token, monkeypatch):
    _mock_orchestrator(monkeypatch)
    r = client.post(
        "/query",
        json={"question": "Is GDPR in force?"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200
    j = r.json()
    assert j["answer"] == "Mock answer about 32016R0679."
    assert j["grounded"] is True
    assert j["sources"][0]["celex"] == "32016R0679"
    assert j["query_log_id"] is not None and isinstance(j["query_log_id"], int)


def test_query_ungrounded_passes_through(client, admin_token, monkeypatch):
    _mock_orchestrator(monkeypatch, answer="Hallucinated 31999R9999.", grounded=False)
    r = client.post(
        "/query",
        json={"question": "q"},
        headers=auth_headers(admin_token),
    )
    j = r.json()
    assert j["grounded"] is False
    assert "31999R9999" in j["ungrounded_celex"]


def test_query_with_filters_and_top_k(client, admin_token, monkeypatch):
    captured = {}

    def fake(
        question,
        *,
        top_k=7,
        filters=None,
        include_repealed=False,
        session_id=None,
        dataset_ids=None,
        document_ids=None,
    ):
        captured["top_k"] = top_k
        captured["filters"] = filters
        captured["include_repealed"] = include_repealed
        return {
            "answer": "ok", "sources": [], "warnings": [], "disclaimer": "d",
            "grounded": True, "ungrounded_celex": [], "model": "mock",
        }

    monkeypatch.setattr("src.api.routes_query.orchestrator.answer_question", fake)
    r = client.post(
        "/query",
        json={
            "question": "q",
            "top_k": 5,
            "include_repealed": True,
            "filters": {"status": "In Force", "subject_matter": "data protection"},
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200
    assert captured["top_k"] == 5
    assert captured["include_repealed"] is True
    assert captured["filters"]["subject_matter"] == "data protection"


# --- history ---------------------------------------------------------------- #

def test_history_returns_user_queries(client, admin_token, monkeypatch):
    _mock_orchestrator(monkeypatch)
    client.post("/query", json={"question": "Q1"}, headers=auth_headers(admin_token))
    client.post("/query", json={"question": "Q2"}, headers=auth_headers(admin_token))
    r = client.get("/history", headers=auth_headers(admin_token))
    assert r.status_code == 200
    h = r.json()
    assert len(h) == 2
    assert h[0]["question"] == "Q2"  # newest first
    assert h[0]["sources"][0]["celex"] == "32016R0679"


def test_history_requires_auth(client):
    assert client.get("/history").status_code == 401


def test_history_is_per_user(client, monkeypatch):
    _mock_orchestrator(monkeypatch)
    # user1 asks
    client.post("/auth/register", json={"username": "user1x", "password": "pass123456"})
    ut = client.post(
        "/auth/login", data={"username": "user1x", "password": "pass123456"}
    ).json()["access_token"]
    client.post("/query", json={"question": "user1 Q"}, headers=auth_headers(ut))
    # user2 asks
    client.post("/auth/register", json={"username": "user2x", "password": "pass123456"})
    u2t = client.post(
        "/auth/login", data={"username": "user2x", "password": "pass123456"}
    ).json()["access_token"]
    client.post("/query", json={"question": "user2 Q"}, headers=auth_headers(u2t))
    # user1 sees only their query
    h = client.get("/history", headers=auth_headers(ut)).json()
    assert len(h) == 1
    assert h[0]["question"] == "user1 Q"


# --- feedback --------------------------------------------------------------- #

def test_feedback_records(client, admin_token, monkeypatch):
    _mock_orchestrator(monkeypatch)
    q = client.post("/query", json={"question": "Q"}, headers=auth_headers(admin_token)).json()
    qid = q["query_log_id"]
    r = client.post(
        "/feedback",
        json={"query_log_id": qid, "rating": 1, "comment": "great"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "recorded"


def test_feedback_requires_auth(client):
    assert client.post("/feedback", json={"rating": 1}).status_code == 401


def test_feedback_bad_rating(client, admin_token):
    r = client.post("/feedback", json={"rating": 5}, headers=auth_headers(admin_token))
    assert r.status_code == 422


# --- chat -------------------------------------------------------------------- #

def test_chat_forwards_document_ids(client, admin_token, monkeypatch):
    captured = {}

    class FakeAgent:
        def answer(self, question, user_id, **kwargs):
            captured["question"] = question
            captured.update(kwargs)
            return {
                "answer": "A sufficiently long mock answer that mentions matching content.",
                "sources": [],
                "warnings": [],
                "disclaimer": "d",
                "grounded": True,
                "ungrounded_celex": [],
                "model": "mock",
            }

    monkeypatch.setattr("src.api.routes_chat.get_qa_agent", lambda: FakeAgent())
    r = client.post(
        "/chat",
        json={
            "question": "What obligations are in my contract?",
            "dataset_ids": [2],
            "document_ids": [5, 6],
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200
    assert captured.get("dataset_ids") == [2]
    assert captured.get("document_ids") == [5, 6]
