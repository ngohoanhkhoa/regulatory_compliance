# EU Regulatory Compliance RAG Chatbot — Technical Document

## 1. Overview

This repository contains a **Retrieval-Augmented Generation (RAG) chatbot** that answers natural-language questions about **EU regulatory obligations**. It is built around the **CEPS EurLex dataset** (~140k legal acts sourced from eur-lex.europa.eu, frozen at August 2019). The core promise is that every answer is **citable**: each response is grounded in retrieved source chunks and annotated with CELEX numbers, act names, Eur-Lex links, and status metadata.

The application is designed to run **locally first**: ingestion, vector search, keyword search, auth, and audit logging all execute on the local machine. The only outbound network call is the final prompt sent to the configured LLM API for answer generation.

> **Current auth status:** Authentication has been disabled for the local-Docker deployment scenario. The backend returns a dummy user for every request, and the frontend no longer presents a login screen.

---

## 2. Features

### 2.1 Core Chat Features
- **Multi-intent routing:** questions are classified as `qa`, `explore`, or `greeting` and routed to specialized agents.
- **Hybrid retrieval:** combines dense vector search (ChromaDB), sparse BM25 keyword search, reciprocal rank fusion, and an LLM-based cross-encoder reranker.
- **Citable answers:** assistant responses include numbered footnotes linked to source cards showing CELEX, act name, status, and excerpt.
- **Grounding guardrail:** the system detects when the generated answer references CELEX numbers that were not present in the retrieved context.
- **Source panel:** expandable accordion of retrieved sources with metadata badges (`In Force`, repealed, etc.).
- **Warnings & disclaimers:** automatically surfaces low-confidence answers and the August 2019 data cutoff notice.
- **Feedback:** users can submit thumbs-up / thumbs-down feedback on answers.

### 2.2 History & Audit
- **Per-user query history:** every question, answer, sources, grounding status, and model name is stored in SQLite.
- **History UI:** browse past queries with expand/collapse, timestamps, and grounding indicators.
- **Audit log:** the `query_log` table serves as an immutable audit trail.

### 2.3 Ingestion & Indexing
- **M1 pipeline:** CSV loading → text cleaning → chunking → parquet output.
- **M2 embedding:** chunk embedding via OpenRouter (`text-embedding-3-small`) and indexing into ChromaDB.
- **Configurable chunking:** min/max token sizes, overlap ratio, and minimum text length are tunable via environment variables.
- **Smoke-test support:** ingestion can be limited to N rows for quick validation.

### 2.4 Frontend
- **Single-page application:** React 18 + Vite + React Router.
- **Pages:** Chat, History, Settings (Dashboard was planned in the UI modernization spec).
- **Settings:** toggle for including repealed/superseded acts in retrieval.

### 2.5 Operations
- **Health endpoint:** `/health` reports status of vector store, chunks parquet, raw CSV, API key, and database.
- **Docker Compose deployment:** backend + frontend + Caddy reverse proxy with one command.
- **Evaluation harness:** `tests/eval_retrieval.py` computes recall@k against the built vector store.

---

## 3. Architecture

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                            │
└───────────────┬─────────────────────────────────┬───────────────┘
                │ HTTPS                           │
                ▼                                 ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│  Caddy Reverse Proxy     │         │  Vite Dev Server         │
│  (:80 / :443)            │         │  (:5173)                 │
└──────────────┬───────────┘         └─────────────┬────────────┘
               │                                    │
               └──────────────┬─────────────────────┘
                              │
                              ▼
               ┌────────────────────────────┐
               │   FastAPI Backend (:8000)  │
               │  - auth (disabled)         │
               │  - chat / query            │
               │  - history / feedback      │
               │  - ingest (admin)          │
               │  - health                  │
               └─────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────────┐   ┌──────────────┐
│  ChromaDB    │   │   SQLite         │   │  OpenCode    │
│  Vector Store│   │   metadata.db    │   │  Go API      │
│  (.vector_   │   │   (query log,    │   │  (LLM gen)   │
│   store/)    │   │   feedback)      │   │              │
└──────────────┘   └──────────────────┘   └──────────────┘
```

### 3.2 Request Flow for a Chat Query

1. **Frontend** `POST /chat` with the user question.
2. **Backend** classifies intent (`qa` / `explore` / `greeting`).
3. **Agent** is selected:
   - `qa_agent` → hybrid retrieval → LLM answer generation.
   - `explore_agent` → dataset aggregation / counting.
   - `greeting_agent` → static friendly response.
4. **Refiner** (`refiner_agent`) polishes the raw answer.
5. **Orchestrator / citation formatter** adds citations, warnings, disclaimer, and grounding check.
6. **Audit logger** writes the full record to `query_log` in SQLite.
7. **Response** returns `answer`, `sources`, `warnings`, `disclaimer`, `grounded`, `model`, `query_log_id`, and `intent`.

---

## 4. Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Backend language | Python 3.12 | Core application logic |
| Dependency mgmt | uv | Fast Python package management |
| Web framework | FastAPI | REST API + auto-generated OpenAPI docs |
| Server | uvicorn | ASGI server |
| Data loading | polars | Lazy CSV reading and transformations |
| Vector store | ChromaDB | Dense retrieval with embeddings |
| Sparse retrieval | rank_bm25 | In-memory BM25 keyword search |
| Embeddings | OpenRouter API | `text-embedding-3-small` |
| Reranker | OpenRouter API | `gpt-4.1-mini` (LLM-based pair-wise rerank) |
| LLM | OpenCode Go API | `deepseek-v4-pro` (OpenAI-compatible) |
| Auth (disabled) | JWT + bcrypt | Originally used for user sessions |
| Metadata/audit | SQLite | Users, query history, feedback |
| Frontend | React 18 + Vite | SPA |
| Routing | React Router | Client-side navigation |
| Reverse proxy | Caddy 2 | HTTPS + routing in Docker |
| Containerization | Docker + Compose | One-command deployment |

---

## 5. Project Structure

```
regulatory_compliance/
├── data/
│   ├── raw/                        # EurLex CSV (not committed)
│   └── processed/                  # chunks.parquet, metadata.db, ingestion_log.json
├── frontend/                       # React SPA
│   ├── src/
│   │   ├── api/                    # client.js, AuthContext.jsx, settings.js
│   │   ├── pages/                  # Chat.jsx, History.jsx, Settings.jsx
│   │   ├── styles/                 # main.css
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── prompts/
│   └── system_prompt.md            # Versioned LLM system prompt
├── scripts/
│   ├── run_ingestion.sh            # Run M1 ingestion pipeline
│   └── run_server.sh               # Start uvicorn backend
├── src/
│   ├── api/                        # FastAPI app and routers
│   │   ├── main.py
│   │   ├── routes_auth.py
│   │   ├── routes_chat.py
│   │   ├── routes_query.py
│   │   ├── routes_admin.py        # corpus stats / add / delete (admin)
│   │   └── schemas.py
│   ├── auth/                       # Auth models, security, dependencies
│   │   ├── models.py
│   │   ├── security.py
│   │   └── dependencies.py         # Currently bypasses auth
│   ├── agents/                     # Intent router + specialized agents
│   │   ├── intent_router.py
│   │   ├── qa_agent.py
│   │   ├── explore_agent.py
│   │   ├── greeting_agent.py
│   │   └── refiner_agent.py
│   ├── generation/                 # LLM client, prompt builder, orchestrator
│   │   ├── llm_client.py
│   │   ├── prompt_builder.py
│   │   ├── citation_formatter.py
│   │   └── orchestrator.py
│   ├── ingestion/                  # Data loading, cleaning, chunking, embedding
│   │   ├── load_csv.py
│   │   ├── clean_text.py
│   │   ├── chunker.py
│   │   ├── embed_and_index.py
│   │   ├── pipeline.py
│   │   └── openrouter_embedder.py
│   ├── retrieval/                  # Vector store, BM25, reranker, hybrid retriever
│   │   ├── vector_store.py
│   │   ├── keyword_index.py
│   │   ├── reranker.py
│   │   └── hybrid_retriever.py
│   └── config.py                   # Central configuration
├── tests/                          # Unit, integration, and eval tests
├── Caddyfile
├── Dockerfile
├── Dockerfile.frontend
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 6. Backend Components

### 6.1 API Layer (`src/api/`)

| Router | File | Endpoints | Notes |
|--------|------|-----------|-------|
| Auth | `routes_auth.py` | `/auth/register`, `/auth/login`, `/auth/me` | Still present but bypassed |
| Chat | `routes_chat.py` | `/chat` | Multi-agent orchestration endpoint |
| Query | `routes_query.py` | `/query`, `/acts/{celex}`, `/history`, `/feedback` | Core query + audit |
| Admin | `routes_admin.py` | `/api/admin/corpus/*` | Corpus stats, add (auto-ingest), delete |
| Main | `main.py` | `/health`, `/` | App factory + CORS |

### 6.2 Authentication (`src/auth/`)

- **`models.py`** — SQLite schema and CRUD for `users`, `query_log`, `feedback`.
- **`security.py`** — bcrypt hashing + JWT issue/verify (currently unused).
- **`dependencies.py`** — **Disabled**: returns a static dummy user `{id: 1, username: "local", is_admin: true}` for all requests.

### 6.3 Agents (`src/agents/`)

- **`intent_router.py`** — Classifies incoming questions into `qa`, `explore`, or `greeting`.
- **`qa_agent.py`** — Retrieves relevant chunks via hybrid search and asks the LLM to answer.
- **`explore_agent.py`** — Answers dataset-level questions (counts, lists, aggregations).
- **`greeting_agent.py`** — Handles small-talk greetings.
- **`refiner_agent.py`** — Post-processes raw agent output for tone and clarity.

### 6.4 Generation (`src/generation/`)

- **`llm_client.py`** — OpenAI-compatible client for the OpenCode Go API with retries/backoff.
- **`prompt_builder.py`** — Assembles system prompt + question + retrieved context.
- **`citation_formatter.py`** — Adds numbered citations, warnings, and disclaimer.
- **`orchestrator.py`** — High-level `answer_question()` flow used by `/query`.

### 6.5 Retrieval (`src/retrieval/`)

- **`vector_store.py`** — ChromaDB wrapper for dense embedding search.
- **`keyword_index.py`** — BM25 index over chunk text.
- **`hybrid_retriever.py`** — Combines vector + BM25 results with Reciprocal Rank Fusion (RRF).
- **`reranker.py`** — LLM-based cross-encoder reranking of the top candidate set.

### 6.6 Ingestion (`src/ingestion/`)

- **`load_csv.py`** — Lazy CSV loading with polars.
- **`clean_text.py`** — HTML/unusual-character cleaning.
- **`chunker.py`** — Splits acts into overlapping token-bounded chunks.
- **`embed_and_index.py`** — Embeds chunks and upserts into ChromaDB.
- **`pipeline.py`** — Orchestrates M1 cleaning + chunking.
- **`openrouter_embedder.py`** — Batches text and calls OpenRouter embeddings API.

### 6.7 Configuration (`src/config.py`)

A single source of truth for:
- File paths (`RAW_CSV_PATH`, `PROCESSED_CHUNKS_PATH`, `VECTOR_STORE_DIR`, `METADATA_DB_PATH`)
- Chunking parameters (`CHUNK_MIN_TOKENS`, `CHUNK_MAX_TOKENS`, `CHUNK_OVERLAP_RATIO`)
- Retrieval parameters (`DEFAULT_TOP_K`, `RERANK_CANDIDATE_K`)
- API keys and model names (`OPENCODE_GO_API_KEY`, `OPENROUTER_API_KEY`)
- Auth secrets (`JWT_SECRET`)

All values are overridable via environment variables loaded from `.env`.

---

## 7. Frontend Components

### 7.1 Structure (`frontend/src/`)

| Directory | Contents |
|-----------|----------|
| `api/` | API client, auth context, settings store |
| `pages/` | Login, Chat, History, Settings |
| `styles/` | Global CSS with design-system variables |

### 7.2 Pages

- **`Login.jsx`** — Login/register form (currently unreachable since auth is disabled).
- **`Chat.jsx`** — Main chat interface: message list, input, sources accordion, feedback buttons.
- **`History.jsx`** — Scrollable list of past queries with expand/collapse.
- **`Settings.jsx`** — Toggle for including repealed/superseded acts.

### 7.3 State Management

- **`AuthContext.jsx`** — Provides a dummy user to the component tree.
- **`settings.js`** — Reads/writes user preferences to `localStorage`.
- **`client.js`** — Fetch wrapper for all backend calls.

### 7.4 Styling

- **`main.css`** — Dark-themed design system with CSS custom properties for colors, spacing, radii, shadows, and animations.

---

## 8. API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | Health status and component checks |
| `/` | GET | None | Service info |
| `/auth/register` | POST | None | Register a user (bypassed) |
| `/auth/login` | POST | None | Login (bypassed) |
| `/auth/me` | GET | None | Current user info |
| `/chat` | POST | None | Ask a question via multi-agent pipeline |
| `/query` | POST | None | Direct query endpoint |
| `/acts/{celex}` | GET | None | Full metadata + cleaned text for one act |
| `/history` | GET | None | Query history for dummy user |
| `/feedback` | POST | None | Submit thumbs up/down feedback |
| `/api/admin/corpus/acts` | POST | Admin | Add regulatory text (auto-ingest) |

Interactive Swagger UI is available at `/docs` when the backend is running.

---

## 9. Data Model

### 9.1 SQLite Tables

**`users`**
- `id` (PK)
- `username` (unique)
- `hashed_password`
- `is_admin`
- `created_at`

**`query_log`**
- `id` (PK)
- `user_id` (FK)
- `question`
- `answer`
- `sources` (JSON array)
- `grounded` (boolean)
- `model`
- `created_at`

**`feedback`**
- `id` (PK)
- `user_id` (FK)
- `query_log_id` (FK)
- `rating` (+1 / -1)
- `comment`
- `created_at`

### 9.2 Chunk Schema (parquet + ChromaDB metadata)

Each chunk contains:
- `chunk_id`
- `celex`
- `act_name`
- `status`
- `date_document`
- `temporal_status`
- `eurovoc`
- `subject_matter`
- `eurlex_link`
- `chunk_text`

---

## 10. Deployment

### 10.1 Local Development

```bash
# 1. Install dependencies
uv sync --extra dev
cd frontend && npm install && cd ..

# 2. Configure
cp .env.example .env
# Edit .env with OPENCODE_GO_API_KEY

# 3. Place dataset
# data/raw/EurLex_regulations_all.csv

# 4. Run ingestion
scripts/run_ingestion.sh
uv run python -m src.ingestion.embed_and_index

# 5. Start backend and frontend (two terminals)
scripts/run_server.sh
cd frontend && npm run dev
```

### 10.2 Docker

```bash
docker compose up --build
```

Services:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- Caddy proxy: http://localhost

### 10.3 Testing

```bash
uv run python -m pytest -q              # unit + integration tests
uv run python -m pytest tests/test_api.py -v  # API tests
uv run ruff check src tests             # linting
```

### 10.4 Retrieval Evaluation

```bash
uv run python -m tests.eval_retrieval --top-k 7
```

---

## 11. Key Design Decisions

1. **Local-first retrieval** — Vector store, BM25 index, and metadata DB all live on disk locally. The corpus never leaves the machine.
2. **Hybrid search** — Dense + sparse + rerank gives better recall than either approach alone on legal text.
3. **Citations by construction** — The prompt explicitly instructs the LLM to cite sources, and a post-hoc guardrail checks grounding.
4. **Minimal ORM** — Plain `sqlite3` is used instead of SQLAlchemy to keep dependencies small and the audit trail transparent.
5. **Single config file** — All tunables live in `src/config.py` and are overridable via `.env`.
6. **Disabled auth for local Docker** — Since the intended deployment is a local Docker environment, authentication was bypassed rather than removed, leaving the original auth machinery intact for future re-enablement.

---

## 12. Planned Improvements

Per the UI modernization spec (`docs/superpowers/specs/2026-08-04-ui-modernization-design.md`), planned frontend work includes:
- Installing `lucide-react` for icons.
- Creating reusable components (Button, Card, Badge, Input, Toggle, IconButton).
- Modernizing the Navbar with icons and a user dropdown.
- Redesigning Login, Chat, History, and Settings pages.
- Adding a Dashboard page with user stats.
- Expanding the CSS design system and improving responsive design.

---

*Document generated: 2026-08-04*
