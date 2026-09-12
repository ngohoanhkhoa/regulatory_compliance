"""Tests for read-only regulatory corpus views (stats + acts listing)."""

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


def test_corpus_stats(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    stats = corpus.corpus_stats(path)
    assert stats["acts"] == 2
    assert stats["chunks"] == 3
    statuses = {s["status"]: s["count"] for s in stats["by_status"]}
    assert statuses["In Force"] == 2
    assert statuses["Not in Force"] == 1


def test_list_acts_filters_and_paginates(tmp_path, monkeypatch):
    path = _seed_parquet(tmp_path, monkeypatch)
    all_acts = corpus.list_acts(path)
    assert all_acts["total"] == 2 == len(all_acts["items"])

    gdpr = corpus.list_acts(path, "gdpr")
    assert gdpr["total"] == 1
    assert gdpr["items"][0]["celex"] == "32016R0679"
    assert gdpr["items"][0]["chunk_count"] == 2

    page = corpus.list_acts(path, limit=1, offset=1)
    assert page["total"] == 2
    assert len(page["items"]) == 1


def test_list_acts_missing_parquet_returns_empty(tmp_path):
    missing = tmp_path / "nope.parquet"
    assert corpus.list_acts(missing) == {"items": [], "total": 0}
    assert corpus.corpus_stats(missing)["acts"] == 0
