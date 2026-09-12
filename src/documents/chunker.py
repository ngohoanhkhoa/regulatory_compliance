"""Simple paragraph-aware chunker for arbitrary user documents.

Unlike the legal-act chunker, user files have no predictable structure, so we
merge paragraphs up to a character ceiling and window anything oversized with a
small overlap. Chunk ids are ``<doc_key>#<index>`` so they can be deleted en
masse from the vector store.
"""

from __future__ import annotations

import re

from src import config

_WS_RE = re.compile(r"[ \t]+")
_PARA_SPLIT_RE = re.compile(r"\n{2,}")


def _normalize(text: str) -> str:
    lines = [_WS_RE.sub(" ", line).strip() for line in (text or "").splitlines()]
    return "\n".join(lines).strip()


def chunk_text(
    text: str,
    doc_key: str,
    *,
    max_tokens: int | None = None,
    overlap_ratio: float | None = None,
) -> list[dict]:
    """Return ``[{chunk_id, chunk_index, chunk_text}, ...]`` (possibly empty)."""
    normalized = _normalize(text)
    if not normalized:
        return []

    max_tokens = max_tokens or config.USER_DOC_MAX_TOKENS
    overlap_ratio = (
        config.USER_DOC_OVERLAP_RATIO if overlap_ratio is None else overlap_ratio
    )
    max_chars = max(200, int(max_tokens * config.CHARS_PER_TOKEN))
    overlap_chars = int(max_chars * overlap_ratio)

    paragraphs = [p.strip() for p in _PARA_SPLIT_RE.split(normalized) if p.strip()]

    blocks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + 2 + len(para) <= max_chars:
            current = f"{current}\n\n{para}"
        else:
            blocks.append(current)
            current = para
    if current:
        blocks.append(current)

    pieces: list[str] = []
    for block in blocks:
        if len(block) <= max_chars:
            pieces.append(block)
            continue
        i = 0
        while i < len(block):
            j = min(len(block), i + max_chars)
            pieces.append(block[i:j])
            if j >= len(block):
                break
            i = max(i + 1, j - overlap_chars)

    return [
        {"chunk_id": f"{doc_key}#{i:04d}", "chunk_index": i, "chunk_text": piece}
        for i, piece in enumerate(pieces)
    ]
