#!/usr/bin/env bash
# Start the FastAPI backend (M8).
# Usage: scripts/run_server.sh            # uvicorn on :8000
#        scripts/run_server.sh --reload   # dev mode
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f "$HOME/.local/bin/env" ]]; then
  source "$HOME/.local/bin/env"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' is required (install from https://astral.sh/uv)" >&2
  exit 1
fi

unset VIRTUAL_ENV
exec uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 "$@"