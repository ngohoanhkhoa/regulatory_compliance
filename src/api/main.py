"""FastAPI app: wires auth, query, ingest routers + /health + CORS (§5, §8).

Run::

    uv run uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import config
from src.api import (
    routes_auth,
    routes_chat,
    routes_datasets,
    routes_documents,
    routes_query,
    routes_topics,
    routes_users,
)
from src.api.schemas import HealthResponse
from src.auth import models

app = FastAPI(
    title="EU Regulatory Compliance RAG Chatbot",
    version="0.1.0",
    description="Citable answers about EU legal obligations (CEPS EurLex, frozen Aug 2019).",
)


@app.on_event("startup")
def _bootstrap() -> None:
    """Ensure the default admin and the built-in regulatory dataset exist."""
    conn = models.get_db()
    try:
        models.ensure_default_admin(conn, username="admin", password="0000")
        models.ensure_system_datasets(conn)
    finally:
        conn.close()

# CORS: allow the frontend (M6) to call the API during development. Tighten in
# production via the env var.
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Liveness/readiness (§8): check vector store, embedding corpus, API key."""
    components: dict[str, Any] = {}

    # vector store reachable?
    components["vector_store"] = (
        "ok" if config.VECTOR_STORE_DIR.exists() else "missing"
    )
    try:
        from src.retrieval.vector_store import VectorStore

        if components["vector_store"] == "ok":
            vs = VectorStore()
            components["vector_store_count"] = vs.count
    except Exception as exc:
        components["vector_store"] = f"error: {exc}"

    # chunks parquet present?
    components["chunks_parquet"] = (
        "ok" if config.PROCESSED_CHUNKS_PATH.exists() else "missing"
    )

    # raw CSV reachable?
    components["raw_csv"] = "ok" if config.RAW_CSV_PATH.exists() else "missing"

    # OpenCode Go API key configured + reachable?
    from src.generation import llm_client

    components["api_key_configured"] = llm_client.is_configured()
    components["api_reachable"] = "unknown"  # can't cheaply ping without cost

    # DB reachable?
    try:
        from src.auth.models import get_db

        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        components["database"] = "ok"
    except Exception as exc:
        components["database"] = f"error: {exc}"

    degraded = (
        components.get("vector_store") != "ok"
        or components.get("api_key_configured") is not True
    )
    return HealthResponse(
        status="degraded" if degraded else "ok",
        components=components,
        config=config.as_dict(),
    )


app.include_router(routes_auth.router)
app.include_router(routes_query.router)
app.include_router(routes_chat.router)
app.include_router(routes_topics.router)
app.include_router(routes_documents.router)
app.include_router(routes_datasets.router)
app.include_router(routes_users.router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "service": "EU Regulatory Compliance RAG Chatbot",
        "docs": "/docs",
        "health": "/health",
    }
