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


class UsernameUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=40)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminUserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    is_admin: bool = False


class AdminUsernameUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=40)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class AdminFlagUpdate(BaseModel):
    is_admin: bool


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
    dataset_ids: list[int] | None = Field(default=None)


class Source(BaseModel):
    celex: str = ""
    act_name: str = ""
    status: str = ""
    link: str = ""
    chunk_excerpt: str = ""
    dataset_id: int | None = None
    dataset_name: str = ""
    filename: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    warnings: list[str]
    disclaimer: str
    grounded: bool
    ungrounded_celex: list[str]
    model: str = ""
    query_log_id: int | None = None
    intent: str = ""


# --- topics ------------------------------------------------------------------ #
class TopicBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    search_query: str | None = Field(default=None, max_length=2000)
    filters: QueryFilters | None = None
    include_repealed: bool = False


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    search_query: str | None = Field(default=None, max_length=2000)
    filters: QueryFilters | None = None
    include_repealed: bool | None = None


class TopicOut(BaseModel):
    id: int
    name: str
    description: str = ""
    search_query: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    include_repealed: bool = False
    created_at: float | None = None
    updated_at: float | None = None


class TopicTimelineItem(BaseModel):
    celex: str
    act_name: str = ""
    status: str = ""
    date_document: str = ""
    temporal_status: str = ""
    eurovoc: str = ""
    subject_matter: str = ""
    link: str = ""
    excerpt: str = ""
    summary: str = ""
    score: float = 0.0


class TopicTimelineResponse(BaseModel):
    topic: TopicOut
    items: list[TopicTimelineItem]
    count: int
    generated_at: float


# --- feedback ---------------------------------------------------------------- #
class FeedbackRequest(BaseModel):
    query_log_id: int | None = None
    rating: int = Field(ge=-1, le=1, description="+1 good, -1 bad")
    comment: str | None = Field(default=None, max_length=2000)


# --- documents --------------------------------------------------------------- #
class DocumentOut(BaseModel):
    id: int
    dataset_id: int | None = None
    filename: str
    content_type: str = ""
    size_bytes: int = 0
    num_chunks: int = 0
    tags: str = ""
    status: str = "ready"
    error: str = ""
    created_at: float | None = None


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=25)


class DocumentSearchResult(BaseModel):
    chunk_id: str
    score: float = 0.0
    text: str = ""
    document_id: int | None = None
    filename: str = ""
    chunk_index: int | None = None


class CorpusStats(BaseModel):
    acts: int
    chunks: int
    vectors: int | None = None
    by_status: list[dict[str, Any]] = Field(default_factory=list)
    data_cutoff_date: str = ""
    raw_csv_present: bool = False
    chunks_parquet_present: bool = False
    vector_store_present: bool = False


# --- datasets ---------------------------------------------------------------- #
class DatasetOut(BaseModel):
    id: int
    name: str
    slug: str = ""
    description: str = ""
    kind: str
    source: str = ""
    status: str = "ready"
    owner_user_id: int | None = None
    is_global: bool = False
    created_at: float | None = None
    updated_at: float | None = None
    items: int = 0
    chunks: int = 0
    vectors: int | None = None


class DatasetImportResult(BaseModel):
    status: str
    dataset: DatasetOut


class DatasetColumn(BaseModel):
    key: str
    label: str


class DatasetActsResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    columns: list[DatasetColumn] = Field(default_factory=list)
    sort: str | None = None
    order: str = "desc"
    limit: int = 25
    offset: int = 0


class DatasetChunk(BaseModel):
    chunk_index: int = 0
    boundary: str = ""
    text: str = ""


class DatasetItem(BaseModel):
    id: str
    title: str = ""
    status: str = ""
    date: str = ""
    type: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    chunks: list[DatasetChunk] = Field(default_factory=list)


# --- health ------------------------------------------------------------------ #
class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    components: dict[str, Any]
    config: dict[str, Any]
