"""Streaming CSV loader for the CEPS EurLex export (~1GB, ~140k rows).

The corpus is too large to load the full `act_raw_text` column eagerly on
constrained hardware (§1.1, §5.1). We use `polars.scan_csv` (lazy) and slice it
into row batches so peak RSS stays bounded by the batch size, not by the whole
file. Only the requested columns are materialised per batch.

All string-ish columns are read as `Utf8` to avoid pandas-style type-coercion
surprises on largely-null metadata (§4 data-quality caveats).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl

from src import config

# Read every column as string: metadata is sparse and would otherwise be
# coerced to int/float and lose null fidelity. We promote to typed fields only
# where needed downstream (dates, links).
_SCHEMA_OVERRIDES: dict[str, pl.DataType] = {col: pl.Utf8 for col in config.CSV_COLUMNS.values()}


def _scan(path: Path = config.RAW_CSV_PATH) -> pl.LazyFrame:
    if not path.exists():
        raise FileNotFoundError(f"CEPS EurLex CSV not found at {path}")
    return pl.scan_csv(
        str(path),
        schema_overrides=_SCHEMA_OVERRIDES,
        ignore_errors=True,
        quote_char='"',
        infer_schema_length=0,
        encoding="utf8",
        truncate_ragged_lines=True,
    )


def columns(path: Path = config.RAW_CSV_PATH) -> list[str]:
    """Return the list of CSV column names (cheap: schema only)."""
    return _scan(path).collect_schema().names()


def row_count(path: Path = config.RAW_CSV_PATH) -> int:
    """Total number of rows without materialising any data column."""
    return int(_scan(path).select(pl.len()).collect().item())


def validate_header(path: Path = config.RAW_CSV_PATH) -> list[str]:
    """Ensure the CSV header contains every required column.

    Returns the list of *missing* column names (empty list == OK).
    """
    present = set(columns(path))
    required = {"CELEX", "Act_name", "act_raw_text", "Status"}
    return sorted(required - present)


def read_sample(path: Path = config.RAW_CSV_PATH, n_rows: int = 100) -> pl.DataFrame:
    """Eagerly read the first `n_rows` rows — for tests and interactive probing."""
    return _scan(path).head(n_rows).collect()


def iter_batches(
    path: Path = config.RAW_CSV_PATH,
    batch_size: int = config.CSV_LOAD_BATCH_SIZE,
    *,
    use_columns: list[str] | None = None,
) -> Iterator[pl.DataFrame]:
    """Yield the corpus as bounded-size DataFrames, column-projected.

    Parameters
    ----------
    use_columns:
        Optional subset of column names to materialise per batch. Defaults to
        all known schema columns. Restricting to the columns actually needed
        by a pipeline stage keeps per-batch RSS minimal.
    """
    total = row_count(path)
    if use_columns is None:
        use_columns = list(config.CSV_COLUMNS.values())
    unknown = sorted(set(use_columns) - set(columns(path)))
    if unknown:
        raise KeyError(f"Requested columns not in CSV: {unknown}")

    lf = _scan(path).select(use_columns)
    for offset in range(0, total, batch_size):
        batch = lf.slice(offset, batch_size).collect()
        if batch.is_empty():
            break
        yield batch


def batch_to_records(batch: pl.DataFrame) -> list[dict[str, Any]]:
    """Convert a polars DataFrame batch to a list of dict records (string-typed)."""
    return [{k: (v if v is not None else None) for k, v in r.items()} for r in batch.to_dicts()]
