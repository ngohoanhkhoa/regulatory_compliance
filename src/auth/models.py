"""SQLite metadata + audit store: users, query history, feedback (§6, §9.3).

Uses plain `sqlite3` (stdlib) — no ORM, keeping dependencies minimal and
debuggable (§6). The DB file lives at `data/processed/metadata.db` so backups
pick it up alongside the parquet (§11).

Tables:
- ``users``            — id, username (unique), hashed_password, is_admin, created_at
- ``query_log``       — per-user audit trail (§9.3): question, answer, sources, timestamps
- ``feedback``         — thumbs up/down + comment on an answer (§8)
- ``topics``           — user-defined regulatory topics with saved search filters

Thread-safety: SQLite connections are per-thread. ``get_db()`` yields a fresh
connection each call (fast for a handful of users per §6).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from src import config

DB_PATH: Path = config.METADATA_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    hashed_password TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS query_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    question      TEXT    NOT NULL,
    answer        TEXT    NOT NULL,
    sources       TEXT    NOT NULL DEFAULT '[]',   -- JSON array
    grounded      INTEGER NOT NULL DEFAULT 1,
    model         TEXT,
    created_at    REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    query_log_id  INTEGER REFERENCES query_log(id),
    rating        INTEGER NOT NULL,   -- +1 good, -1 bad
    comment       TEXT,
    created_at    REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS topics (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id),
    name             TEXT    NOT NULL,
    description      TEXT    NOT NULL DEFAULT '',
    search_query     TEXT    NOT NULL DEFAULT '',
    filters          TEXT    NOT NULL DEFAULT '{}',   -- JSON object
    include_repealed INTEGER NOT NULL DEFAULT 0,
    timeline_refreshed_at REAL,   -- NULL until the topic is first researched
    created_at       REAL    NOT NULL DEFAULT (strftime('%s','now')),
    updated_at       REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS topic_timeline_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id         INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    celex            TEXT    NOT NULL,
    act_name         TEXT    NOT NULL DEFAULT '',
    status           TEXT    NOT NULL DEFAULT '',
    date_document    TEXT    NOT NULL DEFAULT '',
    temporal_status  TEXT    NOT NULL DEFAULT '',
    eurovoc          TEXT    NOT NULL DEFAULT '',
    subject_matter   TEXT    NOT NULL DEFAULT '',
    link             TEXT    NOT NULL DEFAULT '',
    excerpt          TEXT    NOT NULL DEFAULT '',
    summary          TEXT    NOT NULL DEFAULT '',
    score            REAL    NOT NULL DEFAULT 0,
    refreshed_at     REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS datasets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER REFERENCES users(id),        -- NULL = global/system
    name          TEXT    NOT NULL,
    slug          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL DEFAULT '',
    kind          TEXT    NOT NULL DEFAULT 'regulatory', -- 'documents' | 'regulatory'
    source        TEXT    NOT NULL DEFAULT 'import',     -- 'upload' | 'eurlex' | 'import'
    status        TEXT    NOT NULL DEFAULT 'ready',      -- ready | processing | error
    meta          TEXT    NOT NULL DEFAULT '{}',         -- JSON: collection/paths
    created_at    REAL    NOT NULL DEFAULT (strftime('%s','now')),
    updated_at    REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    dataset_id    INTEGER REFERENCES datasets(id),
    filename      TEXT    NOT NULL,
    content_type  TEXT    NOT NULL DEFAULT '',
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    num_chunks    INTEGER NOT NULL DEFAULT 0,
    tags          TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'ready',   -- ready | error
    error         TEXT    NOT NULL DEFAULT '',
    created_at    REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_query_log_user   ON query_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_user     ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_topics_user       ON topics(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_topic_items_topic ON topic_timeline_items(topic_id);
CREATE INDEX IF NOT EXISTS idx_documents_user    ON documents(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_datasets_owner    ON datasets(owner_user_id, created_at DESC);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a DB was first created (no-op if present)."""
    topic_cols = {r["name"] for r in conn.execute("PRAGMA table_info(topics)").fetchall()}
    if "timeline_refreshed_at" not in topic_cols:
        conn.execute("ALTER TABLE topics ADD COLUMN timeline_refreshed_at REAL")

    doc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "dataset_id" not in doc_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN dataset_id INTEGER")
    if "tags" not in doc_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
    conn.commit()


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a row-factory connection, creating the DB + tables if needed."""
    if db_path is None:
        db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


# --- users ------------------------------------------------------------------ #

def create_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    hashed_password: str,
    is_admin: bool = False,
) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, hashed_password, is_admin) VALUES (?,?,?)",
        (username, hashed_password, int(is_admin)),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_name(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    return dict(row) if row else None


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()]


def ensure_default_admin(
    conn: sqlite3.Connection,
    username: str = "admin",
    password: str = "0000",
) -> dict[str, Any] | None:
    """Create or update the default admin account.

    Returns the user dict if created/updated, None if it already exists with
    the requested credentials.
    """
    from src.auth import security

    existing = get_user_by_name(conn, username)
    hashed = security.hash_password(password)

    if existing is None:
        uid = create_user(
            conn,
            username=username,
            hashed_password=hashed,
            is_admin=True,
        )
        return get_user_by_id(conn, uid)

    # Reset password and ensure admin flag for the default account.
    conn.execute(
        "UPDATE users SET hashed_password = ?, is_admin = 1 WHERE id = ?",
        (hashed, existing["id"]),
    )
    conn.commit()
    return get_user_by_id(conn, existing["id"])


# --- query log --------------------------------------------------------------- #

def log_query(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    question: str,
    answer: str,
    sources: list[dict],
    grounded: bool,
    model: str | None,
) -> int:
    cur = conn.execute(
        "INSERT INTO query_log (user_id, question, answer, sources, grounded, model) "
        "VALUES (?,?,?,?,?,?)",
        (user_id, question, answer, json.dumps(sources), int(grounded), model),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_history(
    conn: sqlite3.Connection, user_id: int, limit: int = 50
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM query_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.get("sources") or "[]")
        d["grounded"] = bool(d.get("grounded"))
        out.append(d)
    return out


def delete_query_log(
    conn: sqlite3.Connection, user_id: int, query_log_id: int
) -> bool:
    """Delete one query-log entry owned by ``user_id``.

    Also removes any feedback rows that reference it. Returns True if a row
    was deleted, False if it did not exist for that user.
    """
    row = conn.execute(
        "SELECT id FROM query_log WHERE id = ? AND user_id = ?",
        (query_log_id, user_id),
    ).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM feedback WHERE query_log_id = ?", (query_log_id,))
    conn.execute("DELETE FROM query_log WHERE id = ? AND user_id = ?", (query_log_id, user_id))
    conn.commit()
    return True


# --- feedback --------------------------------------------------------------- #

def add_feedback(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    query_log_id: int | None,
    rating: int,
    comment: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO feedback (user_id, query_log_id, rating, comment) VALUES (?,?,?,?)",
        (user_id, query_log_id, rating, comment),
    )
    conn.commit()
    return int(cur.lastrowid)


# --- topics ------------------------------------------------------------------ #

def _topic_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["filters"] = json.loads(d.get("filters") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["filters"] = {}
    d["include_repealed"] = bool(d.get("include_repealed"))
    return d


def create_topic(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    name: str,
    description: str = "",
    search_query: str = "",
    filters: dict[str, Any] | None = None,
    include_repealed: bool = False,
) -> int:
    cur = conn.execute(
        "INSERT INTO topics "
        "(user_id, name, description, search_query, filters, include_repealed) "
        "VALUES (?,?,?,?,?,?)",
        (
            user_id,
            name,
            description,
            search_query,
            json.dumps(filters or {}),
            int(include_repealed),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_topics(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM topics WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [_topic_row_to_dict(r) for r in rows]


def get_topic(
    conn: sqlite3.Connection, user_id: int, topic_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM topics WHERE id = ? AND user_id = ?", (topic_id, user_id)
    ).fetchone()
    return _topic_row_to_dict(row) if row else None


def update_topic(
    conn: sqlite3.Connection,
    user_id: int,
    topic_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    search_query: str | None = None,
    filters: dict[str, Any] | None = None,
    include_repealed: bool | None = None,
) -> bool:
    """Patch the provided fields for one topic owned by ``user_id``."""
    fields: list[str] = []
    values: list[Any] = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if search_query is not None:
        fields.append("search_query = ?")
        values.append(search_query)
    if filters is not None:
        fields.append("filters = ?")
        values.append(json.dumps(filters))
    if include_repealed is not None:
        fields.append("include_repealed = ?")
        values.append(int(include_repealed))
    if not fields:
        return False
    fields.append("updated_at = strftime('%s','now')")
    values.extend([topic_id, user_id])
    cur = conn.execute(
        f"UPDATE topics SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
        tuple(values),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_topic(conn: sqlite3.Connection, user_id: int, topic_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM topics WHERE id = ? AND user_id = ?", (topic_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


# --- topic timeline items ---------------------------------------------------- #

_ITEM_FIELDS = (
    "celex",
    "act_name",
    "status",
    "date_document",
    "temporal_status",
    "eurovoc",
    "subject_matter",
    "link",
    "excerpt",
    "summary",
    "score",
)


def replace_topic_timeline(
    conn: sqlite3.Connection,
    topic_id: int,
    items: list[dict[str, Any]],
    *,
    refreshed_at: float | None = None,
) -> float:
    """Replace all stored timeline items for ``topic_id``.

    Items are inserted in the given order (newest → oldest), so fetching by id
    preserves that order. Returns the refresh timestamp applied to all rows.
    """
    ts = time.time() if refreshed_at is None else refreshed_at
    conn.execute("DELETE FROM topic_timeline_items WHERE topic_id = ?", (topic_id,))
    conn.execute(
        "UPDATE topics SET timeline_refreshed_at = ? WHERE id = ?", (ts, topic_id)
    )
    for item in items:
        conn.execute(
            "INSERT INTO topic_timeline_items "
            "(topic_id, celex, act_name, status, date_document, temporal_status, "
            "eurovoc, subject_matter, link, excerpt, summary, score, refreshed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                topic_id,
                str(item.get("celex") or ""),
                str(item.get("act_name") or ""),
                str(item.get("status") or ""),
                str(item.get("date_document") or ""),
                str(item.get("temporal_status") or ""),
                str(item.get("eurovoc") or ""),
                str(item.get("subject_matter") or ""),
                str(item.get("link") or ""),
                str(item.get("excerpt") or ""),
                str(item.get("summary") or ""),
                float(item.get("score") or 0.0),
                ts,
            ),
        )
    conn.commit()
    return ts


def get_topic_timeline(conn: sqlite3.Connection, topic_id: int) -> list[dict[str, Any]]:
    """Return stored timeline items for ``topic_id`` in insertion order."""
    rows = conn.execute(
        "SELECT * FROM topic_timeline_items WHERE topic_id = ? ORDER BY id",
        (topic_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_topic_timeline_refreshed_at(
    conn: sqlite3.Connection, topic_id: int
) -> float | None:
    row = conn.execute(
        "SELECT timeline_refreshed_at AS ts FROM topics WHERE id = ?",
        (topic_id,),
    ).fetchone()
    return float(row["ts"]) if row and row["ts"] is not None else None


# --- datasets ---------------------------------------------------------------- #

def create_dataset(
    conn: sqlite3.Connection,
    *,
    name: str,
    slug: str,
    kind: str,
    source: str,
    owner_user_id: int | None = None,
    description: str = "",
    status: str = "ready",
    meta: dict[str, Any] | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO datasets "
        "(owner_user_id, name, slug, description, kind, source, status, meta) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            owner_user_id,
            name,
            slug,
            description,
            kind,
            source,
            status,
            json.dumps(meta or {}),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _dataset_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["meta"] = json.loads(d.get("meta") or "{}")
    except (TypeError, json.JSONDecodeError):
        d["meta"] = {}
    return d


def get_dataset(conn: sqlite3.Connection, dataset_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return _dataset_row(row) if row else None


def get_dataset_by_slug(conn: sqlite3.Connection, slug: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM datasets WHERE slug = ?", (slug,)).fetchone()
    return _dataset_row(row) if row else None


def list_datasets(
    conn: sqlite3.Connection, *, owner_user_id: int | None = None
) -> list[dict[str, Any]]:
    if owner_user_id is None:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at, id").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM datasets WHERE owner_user_id = ? ORDER BY created_at, id",
            (owner_user_id,),
        ).fetchall()
    return [_dataset_row(r) for r in rows]


def list_datasets_visible(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    """Global regulatory datasets + the requesting user's own document dataset."""
    rows = conn.execute(
        "SELECT * FROM datasets WHERE owner_user_id IS NULL OR owner_user_id = ? "
        "ORDER BY (owner_user_id IS NOT NULL), created_at, id",
        (user_id,),
    ).fetchall()
    return [_dataset_row(r) for r in rows]


def update_dataset(
    conn: sqlite3.Connection,
    dataset_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    meta: dict[str, Any] | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if meta is not None:
        fields.append("meta = ?")
        params.append(json.dumps(meta))
    if not fields:
        return False
    fields.append("updated_at = strftime('%s','now')")
    params.append(dataset_id)
    cur = conn.execute(
        f"UPDATE datasets SET {', '.join(fields)} WHERE id = ?", params
    )
    conn.commit()
    return cur.rowcount > 0


def delete_dataset(conn: sqlite3.Connection, dataset_id: int) -> bool:
    cur = conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    conn.commit()
    return cur.rowcount > 0


def ensure_user_documents_dataset(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """Return (creating if needed) the user's single private documents dataset."""
    slug = f"my-documents-{user_id}"
    existing = get_dataset_by_slug(conn, slug)
    if existing:
        return existing
    from src import config

    did = create_dataset(
        conn,
        owner_user_id=user_id,
        name="My Documents",
        slug=slug,
        kind="documents",
        source="upload",
        description="Your private uploaded documents.",
        meta={"collection": config.USER_DOCS_COLLECTION},
    )
    created = get_dataset(conn, did)
    assert created is not None
    return created


def ensure_system_datasets(conn: sqlite3.Connection) -> dict[str, Any]:
    """Register the built-in EURLEX regulatory dataset (idempotent)."""
    from src import config

    existing = get_dataset_by_slug(conn, config.EURLEX_DATASET_SLUG)
    if existing:
        return existing
    did = create_dataset(
        conn,
        owner_user_id=None,
        name="EURLEX Regulatory Texts",
        slug=config.EURLEX_DATASET_SLUG,
        kind="regulatory",
        source="eurlex",
        description="CEPS EurLex corpus of EU legal acts (frozen export).",
        meta={
            "collection": "eurlex_chunks",
            "chunks_path": str(config.PROCESSED_CHUNKS_PATH),
        },
    )
    created = get_dataset(conn, did)
    assert created is not None
    return created


# --- user documents ---------------------------------------------------------- #

def create_document(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    filename: str,
    content_type: str = "",
    size_bytes: int = 0,
    dataset_id: int | None = None,
    tags: str = "",
    status: str = "processing",
) -> int:
    cur = conn.execute(
        "INSERT INTO documents "
        "(user_id, dataset_id, filename, content_type, size_bytes, tags, status) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, dataset_id, filename, content_type, size_bytes, tags, status),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_document(
    conn: sqlite3.Connection,
    document_id: int,
    *,
    num_chunks: int,
    status: str = "ready",
    error: str = "",
) -> None:
    conn.execute(
        "UPDATE documents SET num_chunks = ?, status = ?, error = ? WHERE id = ?",
        (num_chunks, status, error, document_id),
    )
    conn.commit()


def list_documents(
    conn: sqlite3.Connection, user_id: int, *, dataset_id: int | None = None
) -> list[dict[str, Any]]:
    if dataset_id is None:
        rows = conn.execute(
            "SELECT * FROM documents WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM documents WHERE user_id = ? AND dataset_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (user_id, dataset_id),
        ).fetchall()
    return [dict(r) for r in rows]


def count_documents(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE user_id = ?", (user_id,)
    ).fetchone()
    return int(row["n"]) if row else 0


def get_document(
    conn: sqlite3.Connection, user_id: int, document_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def delete_document_row(
    conn: sqlite3.Connection, user_id: int, document_id: int
) -> bool:
    cur = conn.execute(
        "DELETE FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0
