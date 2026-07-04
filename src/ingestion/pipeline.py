"""M1 ingestion pipeline: CSV -> clean -> chunk -> parquet (§5.1 steps 1-3,5,7).

This module deliberately stops *before* embedding / vector store / BM25 —
those are M2/M3. It validates that loading + cleaning + chunking produce a
traceable chunk store on disk (with offsets and metadata), which everything
later depends on.

Run::

    uv run python -m src.ingestion.pipeline            # full corpus
    uv run python -m src.ingestion.pipeline --sample 500   # quick smoke test

Ingestion is idempotent per (celex, chunk_index) — re-running overwrites the
processed parquet in place (§11). Progress is written to an ingestion log JSON
for auditability (§5.1 step 7).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
from tqdm.auto import tqdm

from src import config
from src.ingestion import clean_text, load_csv
from src.ingestion.chunker import chunk_act

CHUNK_OUTPUT_COLUMNS: tuple[str, ...] = (
    "chunk_id",
    "celex",
    "chunk_index",
    "chunk_text",
    "char_offset_start",
    "char_offset_end",
    "boundary",
    "act_name",
    "status",
    "date_document",
    "temporal_status",
    "eurovoc",
    "subject_matter",
    "eurlex_link",
)


@dataclass
class IngestionStats:
    """Counts collected across a run (written to the ingestion log)."""

    rows_seen: int = 0
    rows_kept: int = 0
    rows_dropped: int = 0
    chunks_produced: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)

    def merge(self, other: IngestionStats) -> None:  # pragma: no cover - trivial
        self.rows_seen += other.rows_seen
        self.rows_kept += other.rows_kept
        self.rows_dropped += other.rows_dropped
        self.chunks_produced += other.chunks_produced
        for k, v in other.drop_reasons.items():
            self.drop_reasons[k] = self.drop_reasons.get(k, 0) + v


def _row_chunks(row: dict[str, Any], stats: IngestionStats) -> list[dict[str, Any]]:
    celex = row.get("CELEX")
    if not celex:
        stats.rows_seen += 1
        stats.rows_dropped += 1
        stats.drop_reasons["missing_celex"] += 1
        return []
    stats.rows_seen += 1
    result = clean_text.clean_row(row.get("act_raw_text") or "")
    if not result.accepted:
        stats.rows_dropped += 1
        reason = result.reason or "unknown"
        stats.drop_reasons[reason] = stats.drop_reasons.get(reason, 0) + 1
        return []
    stats.rows_kept += 1

    chunks = chunk_act(result.text or "", celex)
    out: list[dict[str, Any]] = []
    base = {
        "act_name": row.get("Act_name"),
        "status": row.get("Status"),
        "date_document": row.get("Date_document"),
        "temporal_status": row.get("Temporal_status"),
        "eurovoc": row.get("EUROVOC"),
        "subject_matter": row.get("Subject_matter"),
        "eurlex_link": row.get("Eurlex_link"),
    }
    for c in chunks:
        d = c.to_dict()
        d.update(base)
        out.append(d)
    stats.chunks_produced += len(out)
    return out


def ingest(
    out_path: Path = config.PROCESSED_CHUNKS_PATH,
    *,
    sample: int | None = None,
    batch_size: int = config.CSV_LOAD_BATCH_SIZE,
    log_path: Path = config.INGESTION_LOG_PATH,
) -> IngestionStats:
    """Run the full ingestion. Overwrites `out_path`."""
    missing = load_csv.validate_header()
    if missing:
        raise RuntimeError(f"CSV header missing required columns: {missing}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = IngestionStats()
    all_chunks: list[dict[str, Any]] = []

    use_cols = list(config.CHUNK_METADATA_COLUMNS) + ["act_raw_text"]
    total_rows = load_csv.row_count()
    effective_total = min(total_rows, sample) if sample else total_rows
    pbar = tqdm(total=effective_total, unit="rows", desc="ingest")
    seen = 0
    for batch in load_csv.iter_batches(batch_size=batch_size, use_columns=use_cols):
        if sample and seen >= sample:
            break
        rows = batch.to_dicts()
        for row in rows:
            if sample and seen >= sample:
                break
            seen += 1
            all_chunks.extend(_row_chunks(row, stats))
        pbar.n = min(seen, pbar.total)
        pbar.refresh()
    pbar.close()

    if all_chunks:
        df = pl.DataFrame(all_chunks)
        present = [c for c in CHUNK_OUTPUT_COLUMNS if c in df.columns]
        df = df.select(present)
        df.write_parquet(out_path)
    else:
        pl.DataFrame(schema={c: pl.Utf8 for c in CHUNK_OUTPUT_COLUMNS}).write_parquet(out_path)

    log = {
        "raw_csv": str(config.RAW_CSV_PATH),
        "out_path": str(out_path),
        "rows_seen": stats.rows_seen,
        "rows_kept": stats.rows_kept,
        "rows_dropped": stats.rows_dropped,
        "chunks_produced": stats.chunks_produced,
        "drop_reasons": stats.drop_reasons,
        "data_cutoff_date": config.DATA_CUTOFF_DATE,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2))
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M1 ingestion: clean + chunk the CEPS EurLex CSV")
    ap.add_argument("--sample", type=int, default=None, help="limit to first N rows (smoke test)")
    args = ap.parse_args(argv)
    stats = ingest(sample=args.sample)
    print(
        f"ingested: seen={stats.rows_seen} kept={stats.rows_kept} dropped={stats.rows_dropped} "
        f"chunks={stats.chunks_produced} reasons={stats.drop_reasons}"
    )
    print(f"parquet -> {config.PROCESSED_CHUNKS_PATH}")
    print(f"log     -> {config.INGESTION_LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
