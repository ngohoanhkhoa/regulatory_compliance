# EU Regulatory Compliance RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers questions about EU
regulatory obligations using the **CEPS EurLex dataset** (~140k legal acts from
eur-lex.europa.eu). Every answer is **fully citable** — grounded in retrieved
source text with CELEX numbers, act names, and links.

> **Disclaimer:** The dataset is frozen at **August 2019**. Recent legislation
> may be missing. This tool is **not a source of legal advice** — verify against
> current eur-lex.eu before acting. The disclaimer wording is provisional and
> should be reviewed by a lawyer before any real-world use.

## Architecture

```
Web Frontend (React SPA)
    │ HTTPS
FastAPI Backend (auth, query, ingest, health, feedback)
    ├── Retrieval: hybrid vector (ChromaDB) + BM25 + cross-encoder rerank
    ├── Generation: OpenCode Go API (deepseek-v4-flash, swappable)
    └── Metadata/Audit: SQLite (users, query log, feedback)
```

- **Local-first:** ingestion, embeddings, vector search, BM25, auth, and the
  audit log all run on the local machine. The corpus never leaves the network.
- **Only outbound call:** the prompt (question + retrieved context) goes to
  the OpenCode Go API for final answer generation. Requires internet + API key.

## Quick Start

### Prerequisites
- Python 3.12+ (`uv` manages it automatically)
- [uv](https://astral.sh/uv) for dependency management
- Node.js 18+ (for the frontend)
- ~2GB free disk (embedding model + vector store)

### 1. Clone & install
```bash
git clone <repo-url> regulatory_compliance
cd regulatory_compliance
uv sync --extra dev      # Python deps
cd frontend && npm install && cd ..   # Frontend deps
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env: set OPENCODE_GO_API_KEY (get one at https://opencode.ai/auth)
#            set JWT_SECRET to a random string (openssl rand -hex 32)
```

### 3. Place the dataset
```bash
# Put the CEPS EurLex CSV at:
data/raw/EurLex_regulations_all.csv
```

### 4. Run ingestion (M1+M2: clean → chunk → embed → index)
```bash
# Quick smoke test (1000 rows):
scripts/run_ingestion.sh 1000        # chunks only
uv run python -m src.ingestion.embed_and_index --limit 1000   # + embeddings

# Full corpus (~140k rows, takes ~30min chunking + hours embedding on CPU):
scripts/run_ingestion.sh
uv run python -m src.ingestion.embed_and_index
```

### 5. Start the backend
```bash
scripts/run_server.sh                # uvicorn on :8000
# or dev mode:
scripts/run_server.sh --reload
```

### 6. Start the frontend
```bash
cd frontend && npm run dev            # Vite dev server on :5173
```

Open http://localhost:5173, register (the first user becomes admin), and
start asking questions.

## Docker

```bash
docker compose up --build
# Backend on :8000, frontend on :5173, Caddy reverse proxy on :80
```

## API Endpoints (`/docs` for interactive Swagger UI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/register` | POST | Create account (first user = admin) |
| `/auth/login` | POST | Login (OAuth2 password grant → JWT) |
| `/auth/me` | GET | Current user info |
| `/query` | POST | Ask a question → answer + sources + warnings |
| `/acts/{celex}` | GET | Full metadata + text for one act |
| `/history` | GET | Per-user query history (audit trail) |
| `/api/admin/corpus/acts` | POST | Add regulatory text → auto clean + chunk + embed (admin only) |
| `/api/admin/corpus/acts/{celex}` | DELETE | Remove an act from corpus + vector store (admin only) |
| `/health` | GET | Liveness/readiness check |
| `/feedback` | POST | Thumbs up/down on an answer |

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 (uv-managed) |
| Data loading | polars (lazy/streaming) |
| Embeddings | OpenRouter API (text-embedding-3-small) |
| Vector store | ChromaDB (embedded, local) |
| Keyword index | rank_bm25 (in-memory) |
| Reranker | LLM-based via OpenRouter (gpt-4.1-mini) |
| LLM | OpenCode Go API (deepseek-v4-flash, OpenAI-compatible) |
| Backend | FastAPI + SQLite (no heavy ORM) |
| Frontend | React + Vite (SPA) |
| Reverse proxy | Caddy (HTTPS) |
| Packaging | pyproject.toml + uv / Docker Compose |

## Testing

```bash
uv run python -m pytest -q                      # all tests (excl. live LLM)
uv run python -m pytest tests/test_api.py -v    # API tests
uv run ruff check src tests                     # lint
```

## Evaluation

```bash
# Retrieval recall@k (requires vector store built):
uv run python -m tests.eval_retrieval --top-k 7
```

## Project Structure

```
regulatory_compliance/
├── data/raw/                    # CEPS EurLex CSV (not committed)
├── data/processed/              # chunks.parquet, metadata.db, ingestion_log.json
├── src/
│   ├── ingestion/               # load_csv, clean_text, chunker, embed_and_index, pipeline
│   ├── retrieval/               # vector_store, keyword_index, reranker, hybrid_retriever
│   ├── generation/              # llm_client, prompt_builder, citation_formatter, orchestrator
│   ├── auth/                    # models, security, dependencies
│   └── api/                     # main, routes_auth, routes_query, routes_chat, routes_topics, routes_documents, routes_admin, schemas
├── frontend/                    # React SPA (Vite)
├── prompts/system_prompt.md     # versioned system prompt
├── tests/                       # unit + integration + eval
├── scripts/                     # run_ingestion.sh, run_server.sh
├── Dockerfile, Dockerfile.frontend, docker-compose.yml, Caddyfile
├── pyproject.toml, .env.example
└── README.md
```

## Milestones

- **M1** ✅ CSV loading + cleaning + chunking → `data/processed/chunks.parquet`
- **M2** ✅ Embedding + ChromaDB indexing → `.vector_store/`
- **M3** ✅ Hybrid retrieval (vector + BM25 + RRF + cross-encoder rerank)
- **M4** ✅ OpenCode Go API integration + prompt + citations + grounding guardrail
- **M5** ✅ FastAPI backend (auth, /query, /health, /acts, /history, /feedback, corpus admin)
- **M6** ✅ React frontend (login, chat, sources, history)
- **M7** ✅ Audit logging, grounding guardrail tests, eval suite
- **M8** ✅ Docker Compose + Caddy + run scripts + README

## License

Proprietary.