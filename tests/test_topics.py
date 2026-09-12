"""Tests for the Topics feature: CRUD, per-user isolation, and timelines.

The hybrid retriever is never called — the timeline service is exercised with
injected hits, and the endpoint test stubs ``build_timeline``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.topics import service as topic_service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from src import config
    from src.auth import models

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "METADATA_DB_PATH", db_path)
    monkeypatch.setattr(models, "DB_PATH", db_path)
    from src.api import main as main_mod

    return TestClient(main_mod.app)


def _register_and_login(client, username: str, password: str = "password123") -> str:
    r = client.post("/auth/register", json={"username": username, "password": password})
    # 409 tolerated: the "admin" fixture may have registered first.
    assert r.status_code in (201, 409)
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture()
def admin_token(client):
    return _register_and_login(client, "admin")


@pytest.fixture()
def user_token(client):
    _register_and_login(client, "admin")
    return _register_and_login(client, "user1")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- auth ------------------------------------------------------------------- #

def test_topics_require_auth(client):
    assert client.get("/api/topics").status_code == 401
    assert client.post("/api/topics", json={"name": "x"}).status_code == 401


# --- CRUD ------------------------------------------------------------------- #

def test_create_topic_search_query_is_optional(client, admin_token):
    r = client.post(
        "/api/topics",
        json={"name": "Data protection", "description": "GDPR and friends"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201
    j = r.json()
    assert j["name"] == "Data protection"
    assert j["description"] == "GDPR and friends"
    # No explicit override: the query is derived from name + description.
    assert j["search_query"] == ""
    assert j["filters"] == {}
    assert j["include_repealed"] is False
    assert isinstance(j["id"], int)


def test_create_topic_with_filters_and_query(client, admin_token):
    r = client.post(
        "/api/topics",
        json={
            "name": "AI rules",
            "search_query": "artificial intelligence liability",
            "filters": {"subject_matter": "industrial policy"},
            "include_repealed": True,
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201
    j = r.json()
    assert j["search_query"] == "artificial intelligence liability"
    assert j["filters"] == {"subject_matter": "industrial policy"}
    assert j["include_repealed"] is True


def test_create_topic_requires_name(client, admin_token):
    r = client.post(
        "/api/topics",
        json={"description": "no name"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 422


def test_list_and_get_topic(client, admin_token):
    h = auth_headers(admin_token)
    tid = client.post("/api/topics", json={"name": "Energy"}, headers=h).json()["id"]
    listed = client.get("/api/topics", headers=h).json()
    assert [t["id"] for t in listed] == [tid]
    got = client.get(f"/api/topics/{tid}", headers=h)
    assert got.status_code == 200
    assert got.json()["name"] == "Energy"


def test_update_topic(client, admin_token):
    h = auth_headers(admin_token)
    tid = client.post("/api/topics", json={"name": "Energy"}, headers=h).json()["id"]
    r = client.put(
        f"/api/topics/{tid}",
        json={
            "name": "Energy policy",
            "filters": {"eurovoc": "energy"},
            "include_repealed": True,
        },
        headers=h,
    )
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == "Energy policy"
    assert j["filters"] == {"eurovoc": "energy"}
    assert j["include_repealed"] is True
    # untouched field survives the patch
    assert j["description"] == ""


def test_delete_topic(client, admin_token):
    h = auth_headers(admin_token)
    tid = client.post("/api/topics", json={"name": "Temp"}, headers=h).json()["id"]
    r = client.delete(f"/api/topics/{tid}", headers=h)
    assert r.status_code == 200
    assert client.get("/api/topics", headers=h).json() == []
    assert client.get(f"/api/topics/{tid}", headers=h).status_code == 404


def test_get_missing_topic_404(client, admin_token):
    assert client.get("/api/topics/9999", headers=auth_headers(admin_token)).status_code == 404


# --- per-user isolation ----------------------------------------------------- #

def test_topics_are_private(client, admin_token, user_token):
    admin_h = auth_headers(admin_token)
    user_h = auth_headers(user_token)
    tid = client.post("/api/topics", json={"name": "Secret"}, headers=admin_h).json()["id"]

    assert client.get("/api/topics", headers=user_h).json() == []
    assert client.get(f"/api/topics/{tid}", headers=user_h).status_code == 404
    assert client.delete(f"/api/topics/{tid}", headers=user_h).status_code == 404


# --- timeline --------------------------------------------------------------- #

def test_timeline_auto_researches_once_and_persists(client, admin_token, monkeypatch):
    h = auth_headers(admin_token)
    tid = client.post("/api/topics", json={"name": "Data protection"}, headers=h).json()["id"]

    calls = {"n": 0}

    def fake_build(topic, **kw):
        calls["n"] += 1
        return [
            {
                "celex": "32016R0679",
                "act_name": "GDPR",
                "status": "In Force",
                "date_document": "2016-04-27",
                "link": "http://e/1",
                "excerpt": "Article 1 subject matter.",
            }
        ]

    monkeypatch.setattr("src.api.routes_topics.topic_service.build_timeline", fake_build)
    monkeypatch.setattr(
        "src.topics.summarizer.summarize_items",
        lambda name, items, **kw: ["Relates to data protection."],
    )

    r1 = client.get(f"/api/topics/{tid}/timeline", headers=h)
    assert r1.status_code == 200
    j = r1.json()
    assert j["count"] == 1
    assert j["topic"]["id"] == tid
    assert j["items"][0]["celex"] == "32016R0679"
    assert j["items"][0]["summary"] == "Relates to data protection."
    assert j["generated_at"] > 0

    # Second open reads the stored items; research does not run again.
    r2 = client.get(f"/api/topics/{tid}/timeline", headers=h)
    assert r2.status_code == 200
    assert r2.json()["count"] == 1
    assert calls["n"] == 1


def test_refresh_reruns_research(client, admin_token, monkeypatch):
    h = auth_headers(admin_token)
    tid = client.post("/api/topics", json={"name": "Energy"}, headers=h).json()["id"]

    calls = {"n": 0}

    def fake_build(topic, **kw):
        calls["n"] += 1
        return [
            {
                "celex": "32012R0528",
                "act_name": "Biocides",
                "date_document": "2012-05-22",
                "excerpt": "data protection",
            }
        ]

    monkeypatch.setattr("src.api.routes_topics.topic_service.build_timeline", fake_build)
    monkeypatch.setattr(
        "src.topics.summarizer.summarize_items", lambda name, items, **kw: [""]
    )

    client.get(f"/api/topics/{tid}/timeline", headers=h)  # first research
    r = client.post(f"/api/topics/{tid}/refresh", headers=h)  # explicit refresh
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert calls["n"] == 2


def test_timeline_with_no_matches_is_still_marked_researched(
    client, admin_token, monkeypatch
):
    h = auth_headers(admin_token)
    tid = client.post("/api/topics", json={"name": "Nonexistent"}, headers=h).json()["id"]

    calls = {"n": 0}

    def fake_build(topic, **kw):
        calls["n"] += 1
        return []

    monkeypatch.setattr("src.api.routes_topics.topic_service.build_timeline", fake_build)
    monkeypatch.setattr(
        "src.topics.summarizer.summarize_items", lambda name, items, **kw: []
    )

    assert client.get(f"/api/topics/{tid}/timeline", headers=h).json()["count"] == 0
    assert client.get(f"/api/topics/{tid}/timeline", headers=h).json()["count"] == 0
    assert calls["n"] == 1  # empty result is persisted, not re-searched


def test_timeline_missing_topic_404(client, admin_token):
    h = auth_headers(admin_token)
    assert client.get("/api/topics/9999/timeline", headers=h).status_code == 404
    assert client.post("/api/topics/9999/refresh", headers=h).status_code == 404


# --- service logic ---------------------------------------------------------- #

def test_build_timeline_dedupes_by_celex_and_sorts_by_date():
    retrieved = [
        {
            "text": "weaker chunk",
            "rerank_score": 0.5,
            "metadata": {
                "celex": "32016R0679",
                "act_name": "GDPR",
                "date_document": "2016-04-27",
                "status": "In Force",
            },
        },
        {
            "text": "strongest chunk",
            "rerank_score": 0.9,
            "metadata": {
                "celex": "32016R0679",
                "act_name": "GDPR",
                "date_document": "2016-04-27",
                "status": "In Force",
            },
        },
        {
            "text": "directive",
            "rerank_score": 0.7,
            "metadata": {
                "celex": "31995L0046",
                "act_name": "Data Protection Directive",
                "date_document": "1995-10-24",
                "status": "Not in Force",
            },
        },
    ]
    items = topic_service.build_timeline({"name": "data protection"}, retrieved=retrieved)

    # newest → oldest
    assert [i["celex"] for i in items] == ["32016R0679", "31995L0046"]
    gdpr = next(i for i in items if i["celex"] == "32016R0679")
    assert gdpr["score"] == 0.9
    assert gdpr["excerpt"] == "strongest chunk"


def _two_act_retrieved():
    return [
        {
            "text": "older",
            "rerank_score": 0.6,
            "metadata": {
                "celex": "31995L0046",
                "act_name": "Directive",
                "date_document": "1995-10-24",
            },
        },
        {
            "text": "newer",
            "rerank_score": 0.9,
            "metadata": {
                "celex": "32016R0679",
                "act_name": "GDPR",
                "date_document": "2016-04-27",
            },
        },
    ]


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text

    def complete(self, messages, **kw):
        from src.generation.llm_client import LLMResponse

        return LLMResponse(text=self._text, model="fake")


def test_refresh_topic_timeline_attaches_summaries():
    items = topic_service.refresh_topic_timeline(
        {"id": 7, "name": "data protection"},
        retrieved=_two_act_retrieved(),
        llm=_FakeLLM('Here you go:\n["GDPR links here.", "Directive links here."]'),
    )
    assert [i["celex"] for i in items] == ["32016R0679", "31995L0046"]
    assert items[0]["summary"] == "GDPR links here."
    assert items[1]["summary"] == "Directive links here."


def test_topic_query_defaults_to_name_and_description():
    assert (
        topic_service._topic_query({"name": "Energy", "description": "renewables"})
        == "Energy renewables"
    )
    assert (
        topic_service._topic_query(
            {"name": "Energy", "description": "renewables", "search_query": "solar"}
        )
        == "solar"
    )
    assert topic_service._topic_query({"name": "Energy"}) == "Energy"


def test_refresh_reuses_existing_summaries(monkeypatch):
    captured = {}

    def fake_summarize(topic_name, items, **kw):
        captured["items"] = items
        return [f"fresh:{i['celex']}" for i in items]

    monkeypatch.setattr("src.topics.summarizer.summarize_items", fake_summarize)

    items = topic_service.refresh_topic_timeline(
        {"id": 1, "name": "data protection"},
        retrieved=_two_act_retrieved(),
        previous_items=[{"celex": "32016R0679", "summary": "cached GDPR"}],
    )

    # Only the act without a cached summary is sent to the summariser.
    assert [i["celex"] for i in captured["items"]] == ["31995L0046"]
    by_celex = {i["celex"]: i["summary"] for i in items}
    assert by_celex["32016R0679"] == "cached GDPR"
    assert by_celex["31995L0046"] == "fresh:31995L0046"


def test_refresh_topic_timeline_degrades_on_bad_summary_output():
    items = topic_service.refresh_topic_timeline(
        {"id": 7, "name": "data protection"},
        retrieved=_two_act_retrieved(),
        llm=_FakeLLM("sorry, no JSON here"),
    )
    assert [i["summary"] for i in items] == ["", ""]


def test_parse_summaries_handles_noise_and_length():
    from src.topics import summarizer

    assert summarizer._parse_summaries('Sure:\n["a", "b"]\n', 2) == ["a", "b"]
    assert summarizer._parse_summaries("not json", 2) == ["", ""]
    assert summarizer._parse_summaries('["only one"]', 2) == ["only one", ""]


def test_build_timeline_skips_hits_without_celex():
    retrieved = [
        {"text": "no celex", "rerank_score": 0.9, "metadata": {"act_name": "x"}},
    ]
    assert topic_service.build_timeline({"name": "x"}, retrieved=retrieved) == []


def test_date_sort_key_handles_various_formats():
    assert topic_service._date_sort_key("2016-04-27") == "2016-04-27"
    assert topic_service._date_sort_key("24.10.1995") == "1995-10-24"
    assert topic_service._date_sort_key("") == "9999-99-99"
