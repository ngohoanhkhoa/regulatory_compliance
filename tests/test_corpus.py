"""Tests for read-only regulatory corpus views (stats, canonical listing, item)."""

from __future__ import annotations

import polars as pl

from src.corpus import manager as corpus


def _seed_parquet(tmp_path, monkeypatch):
    from src import config

    path = tmp_path / "chunks.parquet"
    pl.DataFrame(
        {
            "chunk_id": ["32016R0679#0000", "32016R0679#0001", "31995L0046#0000"],
            "celex": ["32016R0679", "32016R0679", "31995L0046"],
            "chunk_index": [0, 1, 0],
            "chunk_text": ["Article 1", "Article 2", "Directive text"],
            "char_offset_start": [0, 1, 0],
            "char_offset_end": [1, 2, 1],
            "boundary": ["Article 1", "Article 2", "Article 1"],
            "act_name": ["GDPR", "GDPR", "Data Protection Directive"],
            "status": ["In Force", "In Force", "Not in Force"],
            "date_document": ["2016-04-27", "2016-04-27", "1995-10-24"],
            "temporal_status": ["", "", ""],
            "eurovoc": ["", "", ""],
            "subject_matter": ["", "", ""],
            "eurlex_link": ["http://e/1", "http://e/1", "http://e/2"],
        }
    ).write_parquet(path)
    monkeypatch.setattr(config, "PROCESSED_CHUNKS_PATH", path)
    return path


def _seed_generic(tmp_path):
    """A non-CELEX dataset: title/state/published aliases, id from chunk_id."""
    path = tmp_path / "generic.parquet"
    pl.DataFrame(
        {
            "chunk_id": ["DOC-A#0000", "DOC-A#0001", "DOC-B#0000"],
            "chunk_text": ["alpha", "beta", "gamma"],
            "chunk_index": [0, 1, 0],
            "boundary": ["Section 1", "Section 2", "Section 1"],
            "title": ["Alpha Act", "Alpha Act", "Beta Act"],
            "state": ["current", "current", "repealed"],
            "publication_date": ["2024-02-01", "2024-02-01", "2023-01-01"],
            "doc_type": ["Decision", "Decision", "Regulation"],
        }
    ).write_parquet(path)
    return path


def test_corpus_stats(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    stats = corpus.corpus_stats(path)
    assert stats["acts"] == 2
    assert stats["chunks"] == 3
    statuses = {s["status"]: s["count"] for s in stats["by_status"]}
    assert statuses["In Force"] == 2
    assert statuses["Not in Force"] == 1


def test_list_acts_canonical_and_search(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    all_acts = corpus.list_acts(path)
    assert all_acts["total"] == 2
    assert [c["key"] for c in all_acts["columns"]] == [
        "id",
        "title",
        "status",
        "date",
        "chunks",
    ]
    # default sort: date desc -> GDPR (2016) before Directive (1995)
    assert all_acts["items"][0]["id"] == "32016R0679"
    assert all_acts["items"][0]["title"] == "GDPR"
    assert all_acts["items"][0]["chunks"] == 2

    gdpr = corpus.list_acts(path, "gdpr")
    assert gdpr["total"] == 1
    assert gdpr["items"][0]["id"] == "32016R0679"

    page = corpus.list_acts(path, limit=1, offset=1)
    assert page["total"] == 2
    assert len(page["items"]) == 1


def test_list_acts_sort_ascending(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    asc = corpus.list_acts(path, sort="id", order="asc")
    assert asc["items"][0]["id"] == "31995L0046"
    assert asc["sort"] == "id"
    assert asc["order"] == "asc"

    by_chunks = corpus.list_acts(path, sort="chunks", order="desc")
    assert by_chunks["items"][0]["chunks"] == 2


def test_list_acts_unknown_sort_falls_back(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    res = corpus.list_acts(path, sort="does_not_exist", order=None)
    assert res["sort"] == "date"
    assert res["order"] == "desc"


def test_list_acts_generic_dataset_aliases(tmp_path):
    path = _seed_generic(tmp_path)
    res = corpus.list_acts(path)
    keys = [c["key"] for c in res["columns"]]
    assert keys == ["id", "title", "status", "date", "type", "chunks"]
    assert res["total"] == 2
    ids = {i["id"] for i in res["items"]}
    assert ids == {"DOC-A", "DOC-B"}
    doc_a = next(i for i in res["items"] if i["id"] == "DOC-A")
    assert doc_a["title"] == "Alpha Act"
    assert doc_a["status"] == "current"
    assert doc_a["date"] == "2024-02-01"
    assert doc_a["type"] == "Decision"


def test_get_item_returns_ordered_chunks(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    item = corpus.get_item(path, "32016R0679")
    assert item["id"] == "32016R0679"
    assert item["title"] == "GDPR"
    assert [c["chunk_index"] for c in item["chunks"]] == [0, 1]
    assert item["chunks"][0]["boundary"] == "Article 1"
    assert item["chunks"][0]["text"] == "Article 1"


def test_get_item_missing_raises(tmp_path, monkeypatch):
    import pytest

    path = _seed_parquet(tmp_path, monkeypatch)
    with pytest.raises(KeyError):
        corpus.get_item(path, "39999R9999")


def test_list_acts_missing_parquet_returns_empty(tmp_path):
    missing = tmp_path / "nope.parquet"
    res = corpus.list_acts(missing)
    assert res["items"] == []
    assert res["total"] == 0
    assert corpus.corpus_stats(missing)["acts"] == 0
