import polars as pl
import pytest

from src.retrieval import keyword_index as kw


@pytest.fixture()
def tiny_parquet(tmp_path):
    df = pl.DataFrame(
        {
            "chunk_id": ["C#0000", "C#0001", "C#0002", "C#0003"],
            "celex": ["C1", "C2", "C3", "C4"],
            "chunk_index": [0, 0, 0, 0],
            "chunk_text": [
                "Article 1 Subject matter This Regulation lays down technical "
                "measures for fisheries.",
                "REGULATION (EU) 2016/679 on the protection of natural persons (personal data).",
                "Council Regulation on the conservation of marine ecosystems and fishing gear.",
                "Article 1 amending Regulation (EC) No 1967/2006 ; repealed by later act.",
            ],
            "char_offset_start": [0, 0, 0, 0],
            "char_offset_end": [10, 10, 10, 10],
            "boundary": ["Article 1", "Preamble", "Preamble", "Article 1"],
            "status": ["In Force", "In Force", "In Force", "Not in Force"],
            "date_document": ["2019", "2016", "2019", "2018"],
            "temporal_status": ["", "", "", "2019-01-01"],
            "eurovoc": ["x", "y", "z", "w"],
            "subject_matter": ["a", "b", "c", "d"],
            "eurlex_link": ["u1", "u2", "u3", "u4"],
            "act_name": ["Act1", "Act2", "Act3", "Act4"],
        }
    )
    p = tmp_path / "chunks.parquet"
    df.write_parquet(p)
    return p


def test_tokenize_stops_punct_and_stopwords():
    toks = kw.tokenize("The Regulation (EU) 2016/679 on the protection of natural persons!")
    assert "the" not in toks and "of" not in toks
    assert "regulation" in toks and "2016" in toks
    # "2016" then "679" (split on non-alnum)
    assert "679" in toks


def test_tokenize_empty():
    assert kw.tokenize("") == []


def test_keyword_index_basic_retrieval(tiny_parquet):
    idx = kw.KeywordIndex(tiny_parquet)
    hits = idx.query("protection of natural persons personal data", n_results=2)
    assert hits
    # the GDPR chunk should rank first for that query
    assert hits[0].chunk_id == "C#0001"
    assert hits[0].metadata["celex"] == "C2"


def test_keyword_index_default_filters_repealed(tiny_parquet):
    idx = kw.KeywordIndex(tiny_parquet)
    hits = idx.query("Article 1 amending Regulation", n_results=4)
    celexes = {h.metadata["celex"] for h in hits}
    assert "C4" not in celexes  # Not in Force -> excluded by default


def test_keyword_index_include_repealed(tiny_parquet):
    idx = kw.KeywordIndex(tiny_parquet)
    hits = idx.query("Article 1 amending Regulation", n_results=4, include_repealed=True)
    celexes = {h.metadata["celex"] for h in hits}
    assert "C4" in celexes


def test_keyword_index_empty_query(tiny_parquet):
    idx = kw.KeywordIndex(tiny_parquet)
    assert idx.query("   ", n_results=4) == []


def test_keyword_index_metadata_filter_by_celex(tiny_parquet):
    idx = kw.KeywordIndex(tiny_parquet)
    hits = idx.query("Regulation", n_results=4, filters={"celex": "C2"})
    assert all(h.metadata["celex"] == "C2" for h in hits)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
