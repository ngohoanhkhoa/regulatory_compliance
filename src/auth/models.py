"""SQLite metadata + audit store: users, query history, feedback (§6, §9.3).

Uses plain `sqlite3` (stdlib) — no ORM, keeping dependencies minimal and
debuggable (§6). The DB file lives at `data/processed/metadata.db` so backups
pick it up alongside the parquet (§11).

Tables:
- ``users``            — id, username (unique), hashed_password, is_admin, created_at
- ``query_log``       — per-user audit trail (§9.3): question, answer, sources, timestamps
- ``feedback``         — thumbs up/down + comment on an answer (§8)

Thread-safety: SQLite connections are per-thread. ``get_db()`` yields a fresh
connection each call (fast for a handful of users per §6).
"""

from __future__ import annotations

import json
import sqlite3
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

CREATE INDEX IF NOT EXISTS idx_query_log_user   ON query_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_user     ON feedback(user_id);
"""


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a row-factory connection, creating the DB + tables if needed."""
    if db_path is None:
        db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
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
