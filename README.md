# EU Regulatory Compliance RAG Chatbot

[![CI](<https://github.com/<your-org>/regulatory_compliance/actions/workflows/ci.yml/badge.svg>)](<https://github.com/<your-org>/regulatory_compliance/actions/workflows/ci.yml>)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/node-18%2B-green.svg)](https://nodejs.org/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

A self-hostable, **fully citable** Retrieval-Augmented Generation (RAG) chatbot
for EU regulatory questions. It answers against the **CEPS EurLex** corpus
(~140k legal acts) and any regulatory dataset you import, grounding every
answer in retrieved source text with CELEX numbers, act names, and links.

> **Disclaimer:** the bundled dataset is frozen at **August 2019**; recent
> legislation may be missing. This tool is **not a source of legal advice** —
> verify against current [eur-lex.europa.eu](https://eur-lex.europa.eu) before
> acting.

## Features

- **Citable answers** — hybrid retrieval with a grounding guardrail flags any
  citation that isn't supported by the retrieved context.
- **Hybrid search** — dense vectors (ChromaDB) + BM25 fused with reciprocal
  rank fusion, then reranked.
- **Multi-dataset chat** — pick the datasets to search, and use `@` mentions to
  scope a question to specific documents or regulatory acts.
- **Unified datasets** — private per-user documents and shared regulatory
  collections in one place, with **import/export bundles** (`.rcdataset.zip`)
  for distributing processed text corpora.
- **Document library** — upload PDF/DOCX/TXT/MD/CSV, tag them, and search
  semantically.
- **Topics** — save a topic, get a timeline of matching acts.
- **Auth & audit** — JWT auth, per-user history/feedback, and admin user
  management.
- **Local-first** — ingestion, embeddings, vector search, BM25, auth, and the
  audit log all run on your machine. The only outbound call is the final
  generation request (question + retrieved context) to the configured LLM API.

## Architecture

```
React SPA (Vite)
      │  HTTPS (Caddy)
FastAPI backend
  ├── Retrieval : ChromaDB vectors + BM25 + RRF → LLM rerank
  ├── Generation: OpenCode Go (OpenAI-compatible chat/completions)
  ├── Datasets  : registry + import/export bundles
  ├── Agents    : intent router (Q&A / explore / greeting)
  └── Storage   : SQLite (users, history, topics, datasets) + local vector store
```

## Quick start (Docker)

```bash
git clone https://github.com/ngohoanhkhoa/regulatory_compliance.git
cd regulatory_compliance
cp .env.example .env            # fill in OPENCODE_GO_API_KEY (and OpenRouter key)
docker compose up --build -d
```

- Frontend / reverse proxy: [http://localhost](http://localhost)
- API + Swagger UI: [http://localhost/docs](http://localhost/docs)
- Backend directly: [http://localhost:8000](http://localhost:8000), frontend dev server: [http://localhost:5173](http://localhost:5173)

The first user to **register** becomes an admin, and a bootstrap `admin` account
is created on first start (see [Security](#security)). To serve the regulatory
corpus you must build the index once (below) or import a dataset bundle.

## Quick start (local development)

Prerequisites: Python 3.11–3.12, [uv](https://astral.sh/uv), Node.js 18+.

```bash
uv sync --extra dev
(cd frontend && npm install)
cp .env.example .env            # fill in API keys
```

### Prebuilt corpus (Git LFS)

The repository ships the **processed CEPS EurLex corpus** — the chunked
`data/processed/chunks.parquet` (~190 MB, ~550k chunks) — via
[Git LFS](https://git-lfs.com), so you can skip the CSV download and chunking
steps:

```bash
git lfs install          # once per machine
git lfs pull             # fetch data/processed/chunks.parquet
```

> Cloning without Git LFS gives you a small pointer file instead of the data. If
> `data/processed/chunks.parquet` is only a few lines, run `git lfs pull`.

You still need to build the vector index from it (this calls the embedding API):

```bash
uv run python -m src.ingestion.embed_and_index
```

The SQLite metadata database and the ~2 GB `.vector_store/` are **not** shipped;
they are created locally on first run / first embedding.

### Build the corpus from source (optional)

If you prefer to rebuild from the raw export:

1. Download the CEPS EurLex CSV and place it at
   `data/raw/EurLex_regulations_all.csv` (not committed — it's ~1 GB).
2. Run ingestion (clean → chunk → embed → index):

```bash
# Smoke test on 1000 rows
scripts/run_ingestion.sh 1000
uv run python -m src.ingestion.embed_and_index --limit 1000

# Full corpus (chunking is fast; embedding the whole corpus takes a while)
scripts/run_ingestion.sh
uv run python -m src.ingestion.embed_and_index
```

Alternatively, **import a prepared bundle** in the app (Datasets → Import
regulatory dataset), which skips re-embedding when the bundle ships embeddings.

### Run

```bash
scripts/run_server.sh                 # API on :8000 (add --reload for dev)
cd frontend && npm run dev            # SPA on :5173
```

Open [http://localhost:5173](http://localhost:5173) and start asking questions.

## Configuration

All settings are environment variables (see `.env.example`). Highlights:

| Variable                                                | Default                           | Purpose                                            |
| ------------------------------------------------------- | --------------------------------- | -------------------------------------------------- |
| `OPENCODE_GO_API_KEY`                                 | —                                | LLM API key for generation (**required**)    |
| `OPENCODE_GO_MODEL`                                   | `deepseek-v4-flash`             | Generation model                                   |
| `OPENROUTER_API_KEY`                                  | —                                | Embeddings + reranker API key (**required**) |
| `OPENROUTER_EMBEDDING_MODEL`                          | `openai/text-embedding-3-small` | Embedding model                                    |
| `JWT_SECRET`                                          | `change-me…`                   | JWT signing secret — set a strong random value    |
| `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` | `admin` / `0000`              | Bootstrap admin (change the password)              |
| `DATA_CUTOFF_DATE`                                    | `2019-08-31`                    | Corpus freeze date shown to users                  |
| `CORS_ORIGINS`                                        | localhost origins                 | Allowed browser origins                            |
| `DATASETS_DIR`                                        | `data/datasets`                 | Imported regulatory datasets                       |
| `UPLOAD_DIR`                                          | `data/uploads`                  | Per-user uploaded documents                        |
| `DEFAULT_TOP_K`, `RERANK_CANDIDATE_K`               | `7`, `25`                     | Retrieval sizing                                   |

## API

Interactive docs at `/docs`. Main routes:

| Method              | Path                                                      | Purpose                                      |
| ------------------- | --------------------------------------------------------- | -------------------------------------------- |
| POST                | `/auth/register` · `/auth/login`                     | Account creation / JWT login                 |
| GET                 | `/auth/me`                                              | Current user                                 |
| PUT                 | `/auth/me/username` · `/auth/me/password`            | Self-service account changes                 |
| POST                | `/query` · `/chat`                                   | Ask a question (answer + sources + warnings) |
| GET                 | `/api/datasets`                                         | Datasets visible to the user                 |
| GET                 | `/api/datasets/{id}/acts`                               | Canonical, sortable, paginated items         |
| GET                 | `/api/datasets/{id}/items/{item_id}`                    | One item's metadata + content                |
| POST/GET            | `/api/datasets/import` · `/api/datasets/{id}/export` | Bundle import/export                         |
| GET/POST/DELETE     | `/api/topics…`                                         | Saved topics + timelines                     |
| GET/POST/DELETE     | `/api/documents…`                                      | Personal document library                    |
| GET/POST/PUT/DELETE | `/api/admin/users…`                                    | Admin user management                        |
| GET/DELETE          | `/history`                                              | Per-user query history                       |
| POST                | `/feedback`                                             | Thumbs up/down                               |
| GET                 | `/health`                                               | Liveness/readiness                           |

## Tech stack

| Layer         | Choice                                  |
| ------------- | --------------------------------------- |
| Language      | Python 3.11–3.12 (uv-managed)          |
| Data loading  | polars (lazy/streaming)                 |
| Embeddings    | OpenRouter (`text-embedding-3-small`) |
| Vector store  | ChromaDB (embedded, local)              |
| Keyword index | rank_bm25 (in-memory)                   |
| Reranker      | LLM-based via OpenRouter                |
| Generation    | OpenCode Go (OpenAI-compatible)         |
| Backend       | FastAPI + SQLite                        |
| Frontend      | React + Vite                            |
| Proxy         | Caddy                                   |
| Packaging     | `pyproject.toml` + uv, Docker Compose |

## Project structure

```
regulatory_compliance/
├── src/
│   ├── ingestion/    # load_csv, clean_text, chunker, embed_and_index, pipeline
│   ├── retrieval/    # vector_store, keyword_index, reranker, hybrid + dataset retrieval
│   ├── generation/   # llm_client, prompt_builder, citation_formatter, orchestrator
│   ├── agents/       # intent router + Q&A / explore / greeting agents
│   ├── auth/         # users, JWT security, dependencies
│   ├── datasets/     # registry + import/export bundles
│   ├── documents/    # per-user library (extract, chunk, store)
│   ├── topics/       # saved topics + timelines
│   ├── corpus/       # read-only regulatory corpus views
│   └── api/          # FastAPI app + routers
├── frontend/         # React + Vite SPA
├── prompts/          # versioned system prompt
├── tests/            # pytest unit + integration
├── scripts/          # run_ingestion.sh, run_server.sh
├── Dockerfile, Dockerfile.frontend, docker-compose.yml, Caddyfile
└── pyproject.toml, .env.example, Makefile
```

## Development

```bash
uv run python -m pytest -q           # test suite (network calls are mocked)
uv run ruff check src tests          # lint
make help                            # common tasks
```

Run `make test`, `make lint`, `make frontend-build`, or `make docker-up`.

## Security

- Never commit `.env` or API keys; only `.env.example` is tracked.
- The bootstrap `admin` account uses `0000` by default — **change it** (Settings →
  Account) or set `DEFAULT_ADMIN_PASSWORD` before first run.
- Set a strong `JWT_SECRET` (`openssl rand -hex 32`).
- User documents and the metadata DB may contain sensitive data; protect
  `data/`, `.vector_store/`, and your backups.
- See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and
follow the [Code of Conduct](CODE_OF_CONDUCT.md). Open issues/PRs using the
provided templates.

## License

The **source code** is released under the [MIT License](LICENSE) © 2026 The EU
Regulatory Compliance RAG Chatbot contributors.

### Data

The processed corpus (`data/processed/chunks.parquet`, shipped via Git LFS) is
derived from the **CEPS EurLex** export of EU legal acts on
[eur-lex.europa.eu](https://eur-lex.europa.eu) and is frozen at August 2019.
It is provided for research and informational use; review and comply with the
upstream dataset's terms before redistributing. The raw 1 GB CSV is **not**
included — obtain it from the original source if you want to rebuild the corpus.
