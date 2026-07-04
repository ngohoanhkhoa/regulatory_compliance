"""Pydantic request/response models for the FastAPI API (§8)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- auth -------------------------------------------------------------------- #
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- query ------------------------------------------------------------------- #
class QueryFilters(BaseModel):
    status: str | None = None
    subject_matter: str | None = None
    eurovoc: str | None = None
    authors: str | None = None
    celex: str | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    filters: QueryFilters | None = None
    include_repealed: bool = False
    top_k: int | None = Field(default=None, ge=1, le=25)


class Source(BaseModel):
    celex: str
    act_name: str = ""
    status: str = ""
    link: str = ""
    chunk_excerpt: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    warnings: list[str]
    disclaimer: str
    grounded: bool
    ungrounded_celex: list[str]
    model: str = ""
    query_log_id: int | None = None


# --- acts -------------------------------------------------------------------- #
class ActResponse(BaseModel):
    celex: str
    act_name: str | None = None
    status: str | None = None
    act_type: str | None = None
    date_document: str | None = None
    temporal_status: str | None = None
    eurovoc: str | None = None
    subject_matter: str | None = None
    authors: str | None = None
    treaty: str | None = None
    eurlex_link: str | None = None
    eli_link: str | None = None
    text: str | None = None


# --- feedback ---------------------------------------------------------------- #
class FeedbackRequest(BaseModel):
    query_log_id: int | None = None
    rating: int = Field(ge=-1, le=1, description="+1 good, -1 bad")
    comment: str | None = Field(default=None, max_length=2000)


# --- health ------------------------------------------------------------------ #
class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    components: dict[str, Any]
    config: dict[str, Any]
