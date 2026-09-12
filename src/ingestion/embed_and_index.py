"""M2: embed the M1 chunk parquet and upsert into a local ChromaDB store (§5.2).

- Embeddings run via the OpenRouter API (default model
  ``openai/text-embedding-3-small``).
- The corpus is batch-embedded once during ingestion; at query time only the
  live user question is embedded (§5.2).
- The vector store is ChromaDB in embedded/local mode, persisted under
  `.vector_store/`. Upserts are idempotent by chunk id
  (`<celex>#<chunk_index>`), so re-running ingestion overwrites cleanly (§11).
- Metadata attached to each vector: celex, chunk_index, boundary, status,
  date_document, eurlex_link, act_name, subject_matter, eurovoc,
  temporal_status — everything the retrieval layer needs for filtering and
  citation without re-reading the parquet (§5.1 step 4).

Run::

    uv run python -m src.ingestion.embed_and_index
    uv run python -m src.ingestion.embed_and_index --limit 2000   # smoke test
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import polars as pl
from tqdm.auto import tqdm

from src import config
from src.ingestion.openrouter_embedder import get_openrouter_embedder

# Chroma metadata values must be primitives (str/int/float/bool/None).
# Everything here is already string-typed from M1; just normalise None.
METADATA_FIELDS: tuple[str, ...] = (
    "celex",
    "chunk_index",
    "boundary",
    "status",
    "date_document",
    "temporal_status",
    "eurovoc",
    "subject_matter",
    "eurlex_link",
    "act_name",
)
COLLECTION_NAME = "eurlex_chunks"


class Embedder(Protocol):
    """Minimal embedder interface so tests can inject a fake."""

    def encode(self, texts: list[str], **kwargs: Any) -> Any: ...


def get_embedder() -> Embedder:
    return get_openrouter_embedder()


class _VectorStore:
    """Thin Chroma client wrapper. Kept tiny so the API surface is testable."""

    def __init__(self, persist_dir: Path = config.VECTOR_STORE_DIR) -> None:
        import chromadb

        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))

    def get_or_create_collection(self, name: str = COLLECTION_NAME):
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )


@dataclass
class EmbedStats:
    chunks_seen: int = 0
    chunks_upserted: int = 0
    batches: int = 0

    def merge(self, other: EmbedStats) -> None:  # pragma: no cover - trivial
        self.chunks_seen += other.chunks_seen
        self.chunks_upserted += other.chunks_upserted
        self.batches += other.batches


def _row_meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = {}
    for f in METADATA_FIELDS:
        v = row.get(f)
        meta[f] = "" if v is None else str(v)
    return meta


def embed_index(
    chunks_path: Path = config.PROCESSED_CHUNKS_PATH,
    *,
    limit: int | None = None,
    batch_size: int = config.INGEST_BATCH_SIZE,
    embedder: Embedder | None = None,
    vector_store: _VectorStore | None = None,
) -> EmbedStats:
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"chunks parquet not found at {chunks_path}. Run M1 ingestion first."
        )
    embedder = embedder or get_embedder()
    store = vector_store or _VectorStore()
    coll = store.get_or_create_collection()

    df = pl.read_parquet(chunks_path)
    if limit is not None:
        df = df.head(limit)
    total = df.height
    if total == 0:
        return EmbedStats()

    stats = EmbedStats()
    pbar = tqdm(total=total, unit="chk", desc="embed")
    for s in range(0, total, batch_size):
        e = min(total, s + batch_size)
        sub = df.slice(s, e - s).to_dicts()
        ids = [str(r["chunk_id"]) for r in sub]
        texts = [str(r.get("chunk_text") or "") for r in sub]
        metas = [_row_meta(r) for r in sub]

        vectors = embedder.encode(
            texts, batch_size=min(128, len(texts)), show_progress_bar=False, convert_to_numpy=True
        )

        coll.upsert(ids=ids, embeddings=vectors.tolist(), documents=texts, metadatas=metas)

        stats.chunks_seen += len(sub)
        stats.chunks_upserted += len(sub)
        stats.batches += 1
        pbar.update(len(sub))
    pbar.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M2: embed chunks and index into ChromaDB")
    ap.add_argument("--limit", type=int, default=None, help="cap number of chunks (smoke test)")
    ap.add_argument("--use-openrouter", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    embedder = get_embedder()
    stats = embed_index(limit=args.limit, embedder=embedder)
    print(
        "embedded: "
        f"seen={stats.chunks_seen} upserted={stats.chunks_upserted} "
        f"batches={stats.batches}"
    )
    print(f"vector store -> {config.VECTOR_STORE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
