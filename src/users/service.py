"""Hard-delete a user and all data they own.

Called by the admin user-management API. Deleting a user removes their private
documents (rows, files, and vector chunks), their "My Documents" dataset, their
topics + timeline items, query history, feedback, and finally the user row.
Regulatory datasets (global, owner NULL) are never touched.
"""

from __future__ import annotations

import shutil
import sqlite3
from typing import Any

from src import config
from src.auth import models
from src.documents.store import UserDocsStore


def delete_user_data(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """Delete ``user_id`` and everything they own. Returns a summary."""
    user = models.get_user_by_id(conn, user_id)
    if user is None:
        return {"deleted": False}

    documents = models.list_documents(conn, user_id)
    topics = models.list_topics(conn, user_id)

    # Uploaded files on disk.
    uploads = config.UPLOAD_DIR / str(user_id)
    if uploads.exists():
        shutil.rmtree(uploads, ignore_errors=True)

    # Vector chunks for the user's documents (one call, best-effort).
    try:
        UserDocsStore().delete_user(user_id)
    except Exception:
        pass

    # Rows: children before the user; documents before their dataset.
    conn.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM datasets WHERE owner_user_id = ?", (user_id,))
    conn.execute(
        "DELETE FROM topic_timeline_items WHERE topic_id IN "
        "(SELECT id FROM topics WHERE user_id = ?)",
        (user_id,),
    )
    conn.execute("DELETE FROM topics WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM query_log WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()

    return {
        "deleted": True,
        "user_id": user_id,
        "username": user.get("username", ""),
        "documents_removed": len(documents),
        "topics_removed": len(topics),
    }
