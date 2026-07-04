"""Central configuration: paths, model names, chunk sizes, top-k, and schema.

All tunables live here so downstream code never hard-codes magic numbers or
column names. Values can be overridden via environment variables (loaded from a
local `.env` if present) — see `.env.example`.

The generation-side settings (LLM model, API key) are defined here too, even
though they are only consumed from milestone M4 onward, so the whole pipeline
has a single source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT_DIR: Path = Path(__file__).resolve().parents[1]


# Load a local .env if present (keeps secrets out of the repo). We do a tiny
# manual parse instead of pulling python-dotenv so dependencies stay minimal.
def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv(ROOT_DIR / ".env")

# --------------------------------------------------------------------------- #
# Project paths
# --------------------------------------------------------------------------- #
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
PROMPTS_DIR: Path = ROOT_DIR / "prompts"

RAW_CSV_PATH: Path = Path(
    os.getenv("RAW_CSV_PATH", str(RAW_DIR / "EurLex_regulations_all.csv"))
)
PROCESSED_CHUNKS_PATH: Path = Path(
    os.getenv("PROCESSED_CHUNKS_PATH", str(PROCESSED_DIR / "chunks.parquet"))
)
INGESTION_LOG_PATH: Path = Path(
    os.getenv("INGESTION_LOG_PATH", str(PROCESSED_DIR / "ingestion_log.json"))
)

VECTOR_STORE_DIR: Path = ROOT_DIR / ".vector_store"

# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #
# The CEPS EurLex export is frozen at August 2019 — surfaced to users in every
# answer and in the UI (§5.5, §9).
DATA_CUTOFF_DATE: str = os.getenv("DATA_CUTOFF_DATE", "2019-08-31")

# --------------------------------------------------------------------------- #
# Ingestion / chunking tunables  (§5.3)
# --------------------------------------------------------------------------- #
# Token estimates use a cheap characters-per-token heuristic (see chunker).
CHUNK_MIN_TOKENS: int = int(os.getenv("CHUNK_MIN_TOKENS", "500"))
CHUNK_MAX_TOKENS: int = int(os.getenv("CHUNK_MAX_TOKENS", "800"))
CHUNK_OVERLAP_RATIO: float = float(os.getenv("CHUNK_OVERLAP_RATIO", "0.15"))
CHARS_PER_TOKEN: int = int(os.getenv("CHARS_PER_TOKEN", "4"))

# Text below this many characters (after cleaning) is treated as too
# short / gibberish and the row is skipped (§4 data-quality caveats).
MIN_RAW_TEXT_CHARS: int = int(os.getenv("MIN_RAW_TEXT_CHARS", "200"))

# Ingestion batch size for embedding upsert (used from M2 onward).
INGEST_BATCH_SIZE: int = int(os.getenv("INGEST_BATCH_SIZE", "1000"))

# CSV loading batch size (rows per polars batch) — keeps peak RAM low on the
# ~1GB corpus even though polars itself is lazy/streaming-capable.
CSV_LOAD_BATCH_SIZE: int = int(os.getenv("CSV_LOAD_BATCH_SIZE", "20000"))

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
# As-shipped column names in the CEPS CSV. Note the dataset's own typo:
# `Act_ammends` / `Ammends_links` (the spec text writes them as
# `Act_amends` / `Ammends_links`). We keep the *actual* CSV spelling here as the
# source of truth and expose spec-friendly aliases via COLUMN_ALIASES.
CSV_COLUMNS: dict[str, str] = {
    "celex": "CELEX",
    "act_name": "Act_name",
    "act_type": "Act_type",
    "status": "Status",
    "eurovoc": "EUROVOC",
    "subject_matter": "Subject_matter",
    "treaty": "Treaty",
    "legal_basis_celex": "Legal_basis_celex",
    "authors": "Authors",
    "procedure_number": "Procedure_number",
    "date_document": "Date_document",
    "date_publication": "Date_publication",
    "first_entry_into_force": "First_entry_into_force",
    "temporal_status": "Temporal_status",
    "act_cites": "Act_cites",
    "cites_links": "Cites_links",
    "act_ammends": "Act_ammends",
    "ammends_links": "Ammends_links",
    "eurlex_link": "Eurlex_link",
    "eli_link": "ELI_link",
    "proposal_link": "Proposal_link",
    "oeil_link": "Oeil_link",
    "additional_info": "Additional_info",
    "act_raw_text": "act_raw_text",
}

# Spec-friendly aliases -> actual CSV column name.
COLUMN_ALIASES: dict[str, str] = {
    "act_amends": "Act_ammends",  # spec spelling -> real column
    "amends_links": "Ammends_links",
}

# Metadata attached to every chunk (§5.1 step 4).
CHUNK_METADATA_COLUMNS: tuple[str, ...] = (
    "CELEX",
    "Act_name",
    "Status",
    "Date_document",
    "Temporal_status",
    "EUROVOC",
    "Subject_matter",
    "Eurlex_link",
)

# --------------------------------------------------------------------------- #
# Retrieval / generation (used from M3/M4; defined here for central config)
# --------------------------------------------------------------------------- #
DEFAULT_TOP_K: int = int(os.getenv("DEFAULT_TOP_K", "7"))
RERANK_CANDIDATE_K: int = int(os.getenv("RERANK_CANDIDATE_K", "25"))
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")

# --------------------------------------------------------------------------- #
# Generation (OpenCode Go API) — §5.2
# --------------------------------------------------------------------------- #
OPENCODE_GO_API_KEY: str | None = os.getenv("OPENCODE_GO_API_KEY") or None
# OpenAI-compatible base (https://opencode.ai/docs/go#endpoints). We append
# `/chat/completions` in the client.
OPENCODE_GO_BASE_URL: str = os.getenv(
    "OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1"
)
OPENCODE_GO_MODEL: str = os.getenv("OPENCODE_GO_MODEL", "deepseek-v4-flash")
OPENCODE_GO_MAX_TOKENS: int = int(os.getenv("OPENCODE_GO_MAX_TOKENS", "8192"))
OPENCODE_GO_TEMPERATURE: float = float(os.getenv("OPENCODE_GO_TEMPERATURE", "0.0"))
# Retry/backoff for the 5-hour rolling rate limit (§5.2).
OPENCODE_GO_MAX_RETRIES: int = int(os.getenv("OPENCODE_GO_MAX_RETRIES", "3"))
OPENCODE_GO_TIMEOUT_SEC: float = float(os.getenv("OPENCODE_GO_TIMEOUT_SEC", "120.0"))
SYSTEM_PROMPT_PATH: Path = PROMPTS_DIR / "system_prompt.md"

# --------------------------------------------------------------------------- #
# Auth (M5+) — §6
# --------------------------------------------------------------------------- #
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production-please")
JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
JWT_TTL_MIN: int = int(os.getenv("JWT_TTL_MIN", "720"))  # 12h default

# Metadata/audit DB (§6, §11) — SQLite under data/processed so backups include it.
METADATA_DB_PATH: Path = PROCESSED_DIR / "metadata.db"


def as_dict() -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of the config (for /health, logs)."""
    return {
        "data_cutoff_date": DATA_CUTOFF_DATE,
        "raw_csv_path": str(RAW_CSV_PATH),
        "chunk_min_tokens": CHUNK_MIN_TOKENS,
        "chunk_max_tokens": CHUNK_MAX_TOKENS,
        "chunk_overlap_ratio": CHUNK_OVERLAP_RATIO,
        "min_raw_text_chars": MIN_RAW_TEXT_CHARS,
        "csv_load_batch_size": CSV_LOAD_BATCH_SIZE,
        "embedding_model": EMBEDDING_MODEL,
        "reranker_model": RERANKER_MODEL,
        "default_top_k": DEFAULT_TOP_K,
        "opencode_go_model": OPENCODE_GO_MODEL,
        "has_api_key": bool(OPENCODE_GO_API_KEY),
    }
