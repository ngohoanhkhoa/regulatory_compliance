#!/usr/bin/env bash
# M1 ingestion: clean + chunk the CEPS EurLex CSV into data/processed/chunks.parquet.
# Usage:
#   scripts/run_ingestion.sh                # full corpus (~140k rows)
#   scripts/run_ingestion.sh 2000           # smoke test on first N rows
set -euo pipefail

cd "$(dirname "$0")/.."

# Make uv discoverable if it was installed to ~/.local/bin but not on PATH yet.
if ! command -v uv >/dev/null 2>&1; then
  if [[ -f "$HOME/.local/bin/env" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.local/bin/env"
  fi
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' is required (install from https://astral.sh/uv)" >&2
  exit 1
fi

SAMPLE="${1:-}"
if [[ -n "$SAMPLE" ]]; then
  uv run python -m src.ingestion.pipeline --sample "$SAMPLE"
else
  uv run python -m src.ingestion.pipeline
fi