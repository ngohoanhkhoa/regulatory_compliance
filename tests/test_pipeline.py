from pathlib import Path

import polars as pl
import pytest

from src import config
from src.ingestion import load_csv

RAW = config.RAW_CSV_PATH
has_raw = RAW.exists()


@pytest.fixture()
def tiny_out(tmp_path: Path) -> Path:
    return tmp_path / "chunks.parquet"


def test_validate_header_real_csv():
    if not has_raw:
        pytest.skip("raw CSV not present")
    missing = load_csv.validate_header()
    assert missing == [], f"missing required columns: {missing}"


def test_iter_batches_yields_progressive_data():
    if not has_raw:
        pytest.skip("raw CSV not present")
    batches = list(load_csv.iter_batches(batch_size=1000, use_columns=["CELEX", "act_raw_text"]))
    assert batches
    total = sum(b.height for b in batches)
    assert total == load_csv.row_count()
    first = batches[0].to_dicts()[0]
    assert "CELEX" in first and "act_raw_text" in first


def test_ingest_sample_produces_parquet_and_log(tiny_out):
    if not has_raw:
        pytest.skip("raw CSV not present")
    from src.ingestion import pipeline

    stats = pipeline.ingest(out_path=tiny_out, sample=300)
    assert stats.rows_seen == 300
    df = pl.read_parquet(tiny_out)
    assert df.height == stats.chunks_produced
    assert df.height > 0
    for col in (
        "chunk_id", "celex", "chunk_index", "chunk_text",
        "char_offset_start", "char_offset_end",
    ):
        assert col in df.columns
    # chunk ids carry the parent celex
    sample_id = df.row(0, named=True)["chunk_id"]
    assert "#" in sample_id
    # offsets are sane
    row = df.row(0, named=True)
    assert 0 <= row["char_offset_start"] < row["char_offset_end"]
