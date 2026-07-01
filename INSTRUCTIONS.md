# Technical Specification — EU Regulatory Compliance RAG Chatbot

**Status:** Draft v1.2
**Target:** Production, multi-user web app, local-first data/retrieval with a hosted LLM API
**Audience:** AI coding assistant (vibe-coding brief) + future maintainers

---

## 1. Project Overview

Build a **Retrieval-Augmented Generation (RAG) chatbot** that helps an **enterprise owner / small compliance team** answer questions about EU regulatory obligations by querying the **CEPS EurLex dataset** (a large CSV export of EU legal acts scraped from eur-lex.europa.eu).

The data pipeline, embeddings, and vector store run **entirely on local hardware**. The **generation step** (the LLM that composes the final answer) calls the **OpenCode Go API** (opencode.ai/go), a hosted subscription service exposing open-weight coding/chat models — see §5.2. Every answer must remain **fully citable** (traceable to a specific act / article / CELEX number), and the service must be robust enough to run unattended as a background process.

### 1.1 Local-first, not fully air-gapped
- Data ingestion, chunking, embeddings, vector search, and the audit log all stay **on the local machine** — the compliance corpus itself is never uploaded anywhere.
- The **only outbound traffic** is the prompt sent to the OpenCode Go API for the final answer generation step: this includes the user's question plus the retrieved context chunks (i.e. excerpts of EU legal text, which is public-domain in nature, but the **user's question itself** does leave the machine). Flag this clearly in the README and in the UI disclaimer.
- Requires an active internet connection and an OpenCode Go subscription/API key to answer queries; the retrieval side works offline, generation does not.
- Target machine for the local components: **AMD Ryzen 7 8845HS, 32GB DDR5, RDNA3 iGPU (no dedicated VRAM)**. This still matters for the embedding model choice — see §5.2.
- If full air-gapped operation is needed later, keep the LLM client behind an interface (`src/generation/llm_client.py`) so a local Ollama/llama.cpp backend can be swapped back in without touching the rest of the pipeline.

---

## 2. Goals & Non-Goals

### Goals
- Answer natural-language compliance questions ("Which regulations apply to X?", "Is Regulation (EU) 2016/679 still in force?", "What amended Directive Y?").
- Ground every answer in retrieved source text, with citations (CELEX number, act name, eur-lex link).
- Distinguish **currently in-force** law from repealed/superseded law (`Status`, `Temporal_status`, `Act_amends`).
- Support filtering by date, subject matter, EuroVoc keyword, author institution.
- Serve a **polished, multi-user web UI** (not just a single local chat window) so several people within the enterprise can log in and use it — see §5, §6.

### Non-Goals (v1)
- Not a source of legal advice — outputs must carry a disclaimer.
- No multi-tenant SaaS (separate companies/organizations on one deployment) — multi-*user* within one enterprise is in scope, multi-*tenant* across enterprises is not.
- No real-time scraping of eur-lex.eu (dataset is a static periodic export, refreshed manually).
- No fine-tuning of the LLM — retrieval quality carries the system, not model training.

---

## 3. Users & Core Use Cases

**Primary users:** a non-technical enterprise owner and a small number of colleagues (e.g. legal/compliance, ops, finance) needing quick, sourced answers about EU regulatory obligations relevant to their business, each with their own login and query history.

Use cases:
1. "What EU regulations govern data protection for a company processing customer data?" → retrieve GDPR family, cite CELEX 32016R0679.
2. "Is this regulation still valid?" → check `Status` + `Temporal_status`.
3. "What replaced/amended this regulation?" → traverse `Act_amends` / `Act_cites` graph.
4. "Summarize the obligations in Article X of [act]." → chunk-level retrieval + summarization with citation.
5. "Show me all regulations tagged with [EuroVoc keyword] since 2020." → metadata-filtered search.

---

## 4. Data Source & Schema

Source: CEPS EurLex dataset (Harvard Dataverse), CSV, ~140k rows, one row per legal act.

Key columns used by the pipeline:

| Column | Use in system |
|---|---|
| `CELEX` | Primary key / citation identifier |
| `Act_name` | Display title |
| `act_raw_text` | Full text — chunked and embedded (main retrieval content) |
| `Status` | Filter: "In Force" vs "Not in Force" |
| `Temporal_status` | End-of-validity date, used for freshness warnings |
| `Date_document`, `Date_publication`, `First_entry_into_force` | Temporal filtering/sorting |
| `Act_amends`, `Ammends_links` | Amendment lineage graph |
| `Act_cites`, `Cites_links` | Citation graph (related-acts feature) |
| `EUROVOC`, `Subject_matter` | Topic filters / metadata tags for hybrid search |
| `Authors` | Institutional filter (Commission / Parliament / Council) |
| `Treaty` | Legal basis filter |
| `Eurlex_link`, `ELI_link` | Clickable citation URL in answers |
| `Legal_basis_celex`, `Procedure_number`, `Proposal_link`, `Oeil_link` | Secondary metadata, surfaced on demand |

**Known data quality caveats to handle defensively in code:**
- Not all columns populated for all rows (see counts in codebook) — pipeline must tolerate nulls.
- `act_raw_text` extraction quality varies for older/scanned acts — add a min-length / gibberish filter.
- Non-English acts excluded already by source, but verify with a language-detection sanity check on ingest.
- Dataset frozen at **August 2019** — the system must **always disclose the data cutoff date** to the user and flag that recent legislation may be missing.

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Web Frontend (multi-user)                    │
│         React/Next.js SPA — chat UI, source panel,            │
│         login screen, per-user history                        │
└───────────────────────────┬────────────────────────────────┘
                             │ HTTPS
┌───────────────────────────▼────────────────────────────────┐
│                        FastAPI Backend                        │
│  /auth/*  /query   /ingest   /health   /acts/{celex}  /feedback│
│                    (JWT/session auth middleware)               │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────────┐
│ Retrieval layer│   │ Metadata + user│   │  Audit / Query log │
│ (hybrid search  │   │ store (SQLite/ │   │  per user (SQLite/ │
│  + rerank)      │   │ Postgres)      │   │  Postgres)          │
└───────┬───────┘   └───────────────┘   └───────────────────┘
        │
        ▼
┌───────────────┐        ┌────────────────────┐
│ Vector store    │        │ BM25 keyword index │
│ (ChromaDB)      │        │ (rank_bm25 / SQLite│
│                 │        │  FTS5)              │
└───────┬───────┘        └────────┬────────────┘
        │      merge + cross-encoder rerank │
        └───────────┬──────────────┘
                     ▼
        ┌────────────────────────┐
        │  OpenCode Go API (cloud)│
        │  opencode.ai/go          │
        │  default: DeepSeek V4    │
        │  Flash (swappable)       │
        └────────────────────────┘
                (only outbound call
                 in the whole system)
```

> Everything below the web frontend runs locally (retrieval, reranking, storage, auth). The single external network dependency is the call to OpenCode Go for answer generation.

### 5.1 Ingestion pipeline (offline, run once / on refresh)
1. Load CSV in chunks with `pandas` (or `polars` for speed given file size) — never load the whole `act_raw_text` column eagerly if RAM-constrained.
2. Clean: strip HTML artifacts, normalize whitespace, drop rows with empty/too-short `act_raw_text`.
3. Chunk each act's text (see §5.3), preserving structural anchors (article/recital numbers) where regex-detectable.
4. Attach metadata to every chunk: `CELEX`, `Act_name`, `Status`, `Date_document`, `Temporal_status`, `EUROVOC`, `Subject_matter`, `Eurlex_link`.
5. Embed chunks in batches (see §5.2) and upsert into the vector store.
6. Build/update a BM25 or SQLite FTS5 keyword index in parallel for hybrid search.
7. Write ingestion run metadata (row counts, skipped rows, timestamp) to an ingestion log for auditability.

### 5.2 Model choices

| Component | Recommendation | Notes |
|---|---|---|
| LLM (generation) | **OpenCode Go API** (opencode.ai/go), default model **DeepSeek V4 Flash** | Hosted, subscription-based ($5 first month, then $10/mo, 5-hour rolling request limits per model). Requires an API key and internet access. Start with DeepSeek V4 Flash for speed/cost; keep the model name configurable in `config.py` so it's easy to swap to GLM-5.2 / Qwen3.7 Max / DeepSeek V4 Pro / Kimi K2.7 Code later if quality needs outweigh speed. |
| Embedding model | **`sentence-transformers`**, local — e.g. `all-MiniLM-L6-v2` (fast/small) or `bge-base-en-v1.5` / `bge-small-en-v1.5` (better quality, still CPU-friendly) | Runs entirely on local CPU via the `sentence-transformers` library; batch-embed offline during ingestion, never at query time for the corpus (only the live user question is embedded per query) |
| Reranker (v1, required) | Local cross-encoder (e.g. `bge-reranker-base`, loadable via `sentence-transformers`/`CrossEncoder`) | Included from v1: reranks the merged hybrid candidate set before the top-k goes to generation. Runs locally on CPU; benchmark its added latency and cap candidate count (e.g. rerank top 20–30 → keep top 6–8) to keep it fast enough |

- Embedding stays local for two reasons: it's the bulk of the compute (140k+ rows) and keeps the actual legal corpus off the network; only the final prompt (question + top-k retrieved excerpts) goes to OpenCode Go.
- Handle OpenCode Go's **5-hour rolling rate limits** defensively: implement retry/backoff and a clear user-facing error ("rate limit reached, try again in X minutes") rather than a silent failure.
- Keep the API key in `.env` (never committed), loaded via `config.py`.
- Context window: confirm the chosen model's context length via OpenCode Go's docs and size the retrieved-chunk count (top-k) so question + context + system prompt fit comfortably.

### 5.3 Chunking strategy
- Primary split: by **article/recital boundary** when detectable via regex (`Article \d+`, `Whereas`, `\(\d+\)` recital markers), falling back to token-based sliding window.
- Fallback chunk size: **500–800 tokens**, **~15% overlap**.
- Store `chunk_id`, `celex`, `chunk_index`, `chunk_text`, `char_offset_start/end` for traceability back to the source row.

### 5.4 Retrieval strategy
- **Hybrid search**: vector similarity (semantic) + BM25/FTS5 (exact term match — important for legal citations, article numbers, defined terms).
- **Metadata pre-filtering**: default to `Status = "In Force"` unless the user explicitly asks about historical/repealed law; expose a UI toggle to include repealed acts.
- **Merge & rerank**: reciprocal rank fusion to merge vector + BM25 candidates, then a **cross-encoder reranker (v1, required — see §5.2)** re-scores the merged candidate set for precision.
- Return top-k (default k=6–8) chunks with full metadata to the generation step.

### 5.5 Generation / prompting
- System prompt must instruct the model to:
  - Answer **only** from the provided context chunks.
  - Explicitly say "I don't have enough information in the dataset" if context is insufficient — never fabricate a CELEX number or article.
  - Cite every factual claim with `[Act_name, CELEX, link]`.
  - Flag if the retrieved act's `Status` is "Not in Force" or `Temporal_status` has passed.
  - Include a standing disclaimer: **not legal advice; dataset frozen at August 2019; verify against current eur-lex.eu before acting.** *(This is a generic placeholder — the enterprise owner has not yet confirmed liability language with a lawyer; treat this wording as provisional and swap it out before any real-world/production use. Keep it in the single versioned prompt file below so it's a one-line change, not a code change.)*
- Keep the prompt template in a versioned file (`prompts/system_prompt.md`) so it can be iterated without touching code.

---

## 6. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Ecosystem fit, matches existing dev environment |
| Data loading | `pandas` / `polars` | `polars` preferred if CSV is very large (lower memory footprint) |
| Embeddings | **`sentence-transformers`** (local, CPU) | No external calls for embeddings; runs entirely on-machine |
| Vector store | **ChromaDB** (embedded, local) | Source CSV is **~1GB** (~140k rows) — comfortably within Chroma's single-machine embedded scale; no need for a separate Qdrant service. Batch ingestion in chunks (e.g. 1k–5k rows at a time) to keep peak RAM low during embedding. |
| Keyword index | SQLite FTS5 or `rank_bm25` | Lightweight, no extra service |
| LLM runtime | **OpenCode Go API** (opencode.ai/go), called via plain HTTPS/`requests` or `httpx` | Hosted, subscription-based; only outbound network dependency in the system |
| Backend API | **FastAPI** | Async, typed, easy to containerize; serves both the JSON API and auth |
| Frontend | **React (or Next.js) single-page app** | Polished, multi-user web UI is a stated requirement (not just single-user local chat) — chat view, source/citation panel, login, per-user history. Talks to FastAPI over HTTPS. |
| Auth | FastAPI + `fastapi-users` or a lightweight custom JWT/session layer, users table in the metadata DB | Simple username/password to start (no SSO needed for v1); each user gets their own query history in the audit log |
| Metadata/audit DB | SQLite for v1 (simple, zero-ops); consider **Postgres** if concurrent multi-user writes start to contend | SQLite is fine at the start given the ~1GB corpus and a handful of users; revisit if usage grows |
| Orchestration | Plain custom RAG pipeline (avoid heavy frameworks like LangChain for a system this size — keep dependencies minimal and debuggable) | Easier to reason about and maintain long-term |
| Packaging | `pyproject.toml` + `uv` or `poetry` | Reproducible local environment |
| Optional containerization | Docker Compose (backend + frontend + vector store) | Worth setting up given this is now a multi-user web app rather than a single local script — makes it easier to run behind a reverse proxy (e.g. Caddy/nginx) with HTTPS for LAN/remote access |

---

## 7. Project Structure

```
regulatory_compliance/
├── data/
│   ├── raw/                     # original CEPS EurLex CSV (not committed)
│   └── processed/                # cleaned/chunked parquet files
├── src/
│   ├── ingestion/
│   │   ├── load_csv.py
│   │   ├── clean_text.py
│   │   ├── chunker.py
│   │   └── embed_and_index.py
│   ├── retrieval/
│   │   ├── vector_store.py       # Chroma client wrapper
│   │   ├── keyword_index.py      # BM25/FTS5 wrapper
│   │   ├── reranker.py           # cross-encoder rerank
│   │   └── hybrid_retriever.py
│   ├── generation/
│   │   ├── llm_client.py         # OpenCode Go API wrapper
│   │   ├── prompt_builder.py
│   │   └── citation_formatter.py
│   ├── auth/
│   │   ├── models.py             # user table
│   │   ├── security.py           # password hashing, JWT/session
│   │   └── dependencies.py       # FastAPI auth dependencies
│   ├── api/
│   │   ├── main.py               # FastAPI app
│   │   ├── routes_auth.py
│   │   ├── routes_query.py
│   │   ├── routes_ingest.py
│   │   └── schemas.py            # pydantic models
│   └── config.py                 # paths, model names, chunk sizes, top-k, etc.
├── frontend/                     # React (or Next.js) multi-user web app
│   ├── src/
│   │   ├── components/           # chat window, source/citation panel, login form
│   │   ├── pages/
│   │   └── api/                  # client for the FastAPI backend
│   ├── package.json
│   └── ...
├── prompts/
│   └── system_prompt.md
├── tests/
│   ├── test_chunker.py
│   ├── test_retrieval.py
│   └── test_generation_grounding.py
├── scripts/
│   ├── run_ingestion.sh
│   └── run_server.sh
├── docker-compose.yml            # backend + frontend + vector store, reverse proxy
├── pyproject.toml
├── .env.example                  # OPENCODE_GO_API_KEY, model name, JWT secret, etc.
└── README.md
```

> **Naming note:** the root folder is `regulatory_compliance`, not `eurlex-rag-chatbot`, deliberately — this is meant to host the regulatory-compliance *product* as a whole, so it can later grow additional data sources (beyond CEPS EurLex) and additional functions (beyond this chatbot) without implying it's tied to one dataset or one feature.

---

## 8. API Design (FastAPI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/register` | POST | Create a user account (admin-invited or self-serve, TBD) |
| `/auth/login` | POST | Authenticate, return session/JWT |
| `/auth/me` | GET | Current user info |
| `/query` | POST | `{question, filters?}` → `{answer, sources[], warnings[]}` (auth required; logged against the requesting user) |
| `/acts/{celex}` | GET | Return full metadata + text for a single act |
| `/history` | GET | Current user's past queries/answers |
| `/ingest` | POST | Trigger/re-run ingestion pipeline (admin only) |
| `/health` | GET | Liveness/readiness check (vector store reachable, OpenCode Go reachable) |
| `/feedback` | POST | Log thumbs up/down + optional comment on an answer (for later eval) |

Response schema for `/query` should always include:
```json
{
  "answer": "string",
  "sources": [
    {"celex": "32016R0679", "act_name": "...", "status": "In Force", "link": "...", "chunk_excerpt": "..."}
  ],
  "warnings": ["Dataset frozen at Aug 2019 — verify on eur-lex.eu", "..."],
  "disclaimer": "Not legal advice."
}
```

---

## 9. Compliance-Specific Features (what makes this more than generic RAG)

1. **In-force awareness**: every answer flags whether cited acts are currently valid, using `Status` and `Temporal_status`.
2. **Amendment lineage**: when an act appears in `Act_amends`, surface "this act was later amended by / amends" links so the user isn't relying on a superseded version.
3. **Audit trail**: every query + answer + sources logged to SQLite with timestamp, for the enterprise owner's own compliance record-keeping.
4. **Explicit dataset cutoff disclosure**: shown in the UI persistently, not just in answers.
5. **Grounding guardrail**: reject/flag answers where the model's claim isn't traceable to a retrieved chunk (simple heuristic: does the answer reference a CELEX number that was actually in the retrieved context?).

---

## 10. Testing & Evaluation

- **Unit tests**: chunker correctness, metadata attachment, retrieval filter logic.
- **Retrieval eval set**: hand-curate ~20–30 question/expected-CELEX pairs to check recall@k during development.
- **Grounding eval**: automated check that every CELEX number in a generated answer exists in the retrieved context set (catches hallucination).
- **Latency budget**: target end-to-end response time under ~15–20s for a single query (embedding is local and precomputed; latency is mostly local retrieval + the OpenCode Go API round-trip, which depends on network conditions and API load).

---

## 11. Deployment & Operations

- Runs as a service (`docker-compose up` or `uvicorn` + `systemd`/frontend build served via nginx/Caddy) accessible over the local network to multiple users, with HTTPS via a reverse proxy.
- Ingestion (loading, cleaning, chunking, embedding, indexing) works fully offline once packages/embedding models are downloaded.
- Answering queries requires an internet connection and a valid `OPENCODE_GO_API_KEY` (generation step only).
- Data refresh = re-run `/ingest` when a new CEPS EurLex CSV export is obtained; keep ingestion idempotent (upsert by `CELEX` + `chunk_index`).
- Backups: vector store directory + database (SQLite file or Postgres dump, including the user/auth tables) should be included in the regular backup routine.
- Monitor OpenCode Go subscription/rate-limit status; surface remaining quota or renewal needs in `/health` if the API exposes that info.

---

## 12. Open Questions / Assumptions to confirm before/while building

### Resolved (confirmed by the enterprise owner)
1. **CSV size**: ~1GB (~140k rows) → ChromaDB (embedded, local) is sufficient; no need for Qdrant. Batch ingestion to control peak RAM.
2. **UI**: a **polished, multi-user web UI** is needed, not just a single-user local chat — React/Next.js frontend + FastAPI backend + basic auth, see §5–§8.
3. **Reranking**: yes — cross-encoder reranker is now a **required v1 component**, not optional (§5.2, §5.4).
4. **Default OpenCode Go model**: start with **DeepSeek V4 Flash**; kept configurable in `config.py` to swap later.
5. **Third-party data sharing**: acceptable to send the user's question + retrieved excerpts to OpenCode Go — no further data-retention review requested for now.

### Still open
1. **Disclaimer/liability language**: the enterprise owner has **no confirmed legal wording yet**. The spec currently ships a generic placeholder disclaimer (§5.5) — treat it as provisional and get it reviewed by a lawyer before real-world use; don't let "it's just a placeholder" quietly become the shipped copy.
2. **Auth mechanism details**: simple username/password to start, per §6 — confirm expected number of users and whether self-serve registration or admin-invited accounts fit better.
3. **Hosting/network exposure**: confirm whether the web UI should be reachable only on the local network, or exposed externally (VPN vs. public HTTPS) — this affects the reverse-proxy/auth hardening needed before go-live.

---

## 13. Build Order (suggested milestones for vibe-coding)

1. **M1** — CSV loading + cleaning + chunking pipeline, tested on a data sample.
2. **M2** — Embedding + vector store indexing; verify retrieval quality manually.
3. **M3** — Hybrid retrieval (vector + BM25) + metadata filtering + cross-encoder reranker.
4. **M4** — OpenCode Go API integration (default: DeepSeek V4 Flash) + prompt template + citation formatting.
5. **M5** — FastAPI backend wiring `/query`, `/health`, `/acts/{celex}`, plus `/auth/*` and `/history`.
6. **M6** — React/Next.js web frontend: login, chat view, source/citation panel, per-user history — connected to the backend.
7. **M7** — Audit logging, grounding guardrail, basic eval suite.
8. **M8** — Docker Compose (backend + frontend + vector store) behind a reverse proxy with HTTPS, packaging, run scripts, README, hardening for unattended multi-user operation.