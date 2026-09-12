"""Canonical item schema for regulatory datasets.

Regulatory bundles may carry arbitrary column names (a CEPS export, a partner
export, an imported set). This module maps the well-known aliases onto a small
canonical display model — ``id``/``title``/``status``/``date``/``type``/``chunks``
— so the same list/content UI adapts to any regulatory dataset.

The mapping is intentionally declarative: callers resolve which canonical fields
exist, then build a uniform frame. Nothing here imports polars, keeping it easy
to unit-test.
"""

from __future__ import annotations

# (key, human label) in display order.
CANONICAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("id", "ID"),
    ("title", "Title"),
    ("status", "Status"),
    ("date", "Date"),
    ("type", "Type"),
    ("chunks", "Chunks"),
)

LABELS: dict[str, str] = dict(CANONICAL_FIELDS)

# Recognized source column names per canonical field (case-insensitive).
ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("celex", "item_id", "id", "doc_id", "reference"),
    "title": ("act_name", "title", "name", "act_title", "document_title"),
    "status": ("status", "state"),
    "date": (
        "date_document",
        "date",
        "publication_date",
        "document_date",
        "date_publication",
        "published",
        "published_at",
    ),
    "type": ("act_type", "type", "category", "doc_type", "document_type"),
}

# When no id-like column exists, the item id is derived from this column.
ID_FALLBACK = "chunk_id"
ID_SEPARATOR = "#"


def resolve_columns(columns: list[str]) -> dict[str, str]:
    """Map canonical field -> actual column name, for fields that are present."""
    lowered = {str(c).lower(): str(c) for c in columns}
    resolved: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            actual = lowered.get(alias.lower())
            if actual is not None:
                resolved[field] = actual
                break
    return resolved


def descriptor(resolved: dict[str, str], columns: list[str]) -> list[dict[str, str]]:
    """Describe the canonical columns available for a dataset, in display order.

    ``id`` is available when an alias resolves or a ``chunk_id`` fallback exists;
    ``chunks`` is always available (derived count).
    """
    cols = {str(c) for c in columns}
    out: list[dict[str, str]] = []
    for key, label in CANONICAL_FIELDS:
        if key == "chunks":
            out.append({"key": key, "label": label})
        elif key == "id":
            if "id" in resolved or "id" in cols or ID_FALLBACK in cols:
                out.append({"key": key, "label": label})
        elif key in resolved:
            out.append({"key": key, "label": label})
    return out
