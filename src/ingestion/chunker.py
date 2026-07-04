"""Structural chunker for cleaned EU legal acts (§5.3).

Strategy
--------
1. Primary split on *article* boundaries where a heading is detectable via
   regex (``Article N`` at the start of a line). The pre-`Article 1` preamble
   (date header, recitals) is further split on numbered recital markers
   ``(N)`` — scoped to the preamble so we never fragment article bodies by
   their own ``(N)`` sub-paragraphs.
2. Small adjacent segments are merged to reach ``CHUNK_MIN_TOKENS`` unless
   doing so would exceed ``CHUNK_MAX_TOKENS``.
3. Any segment still larger than the ceiling is split with an overlapping
   sliding window, snapped to the nearest line boundary for readability.
4. Tokens are estimated from characters (``CHARS_PER_TOKEN``); this is a cheap
   stand-in for a real tokenizer and is intentionally conservative.

Every chunk records its position in the original (cleaned) act text via
``char_offset_start`` / ``char_offset_end`` so retrieval hits can be traced back
to the source row (§5.3, §9 audit traceability).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from src import config

# Article heading detection.
#
# The CEPS `act_raw_text` column is exported as a *single flattened line* (no
# newlines), so we cannot anchor headings to the start of a line. Instead we
# exploit the structural difference between a heading and an inline citation:
#
#   heading   : "...previous sentence. Article 2 Scope 1. This Regulation ..."
#   citation  : "Article 43(2) thereof"  /  "Article 290 TFEU"  /  "Article 349 of ..."
#
# A heading is `Article <num> <Capitalised title word>`; a citation is either
# `Article <num>(<n>) ...`, `Article <num> TFEU/<allcaps>`, or `Article <num>`
# followed by a lowercase preposition ("of", "to", "the", "thereof"). The regex
# below matches the heading shape; false positives like "Article 5a No 1"
# (citation numbering) are filtered out in `_anchors`.
_ARTICLE_RE = re.compile(r"(?<![A-Za-z])Article\s+(\d+[a-z]?)\s+([A-Z][a-z]+)\b")
# False-positive title words that actually signal a citation, not a heading.
_NON_TITLE_WORDS = frozenset({"No", "And", "Or", "But", "Of", "To", "In", "On", "For"})

# Recital markers, also mid-line in flattened text, e.g. ". (1) The protection...".
_RECITAL_RE = re.compile(r"(?<![\w)])\((\d+)\)\s+[A-Z]")
_WHEREAS_RE = re.compile(r"(?im)\bWhereas\s*:")


@dataclass
class Chunk:
    """A retrievable slice of one act's cleaned text."""

    chunk_id: str
    celex: str
    chunk_index: int
    chunk_text: str
    char_offset_start: int
    char_offset_end: int
    boundary: str  # "Preamble" | "Article N" | "Recital N" | "window"

    def to_dict(self) -> dict:
        return asdict(self)


def _tokens(s: str) -> float:
    """Cheap token estimate from characters (see config.CHARS_PER_TOKEN)."""
    return len(s) / config.CHARS_PER_TOKEN if s else 0.0


def _anchors(text: str) -> list[tuple[int, str, str]]:
    """Return ``[(pos, label, kind)]`` sorted by position.

    ``kind`` is "article" or "recital". Recital anchors are only picked up
    before the first article so article sub-paragraphs are never fragmented;
    recital splitting is also skipped entirely when the act has no detectable
    article structure (so we fall back to windowing rather than mis-splitting
    article sub-paragraphs).
    """
    article_hits: list[tuple[int, str, str]] = []
    for m in _ARTICLE_RE.finditer(text):
        title = m.group(2)
        if title in _NON_TITLE_WORDS:
            continue
        article_hits.append((m.start(), f"Article {m.group(1)}", "article"))

    if not article_hits:
        return []  # no article structure -> rely on window fallback

    preamble_end = article_hits[0][0]
    whereas = _WHEREAS_RE.search(text)
    recital_floor = whereas.end() if whereas else 0
    recital_hits = [
        (m.start(), f"Recital {m.group(1)}", "recital")
        for m in _RECITAL_RE.finditer(text)
        if recital_floor <= m.start() < preamble_end
    ]
    return sorted(article_hits + recital_hits, key=lambda a: a[0])


def _segments(text: str) -> list[tuple[int, int, str, str]]:
    """Slice text into (start, end, label, raw_slice) segments by anchors."""
    anchors = _anchors(text)
    if not anchors:
        return [(0, len(text), "Preamble", text)]
    starts = [0] + [a[0] for a in anchors]
    ends = [a[0] for a in anchors] + [len(text)]
    labels = ["Preamble"] + [a[1] for a in anchors]
    segs: list[tuple[int, int, str, str]] = []
    for s, e, label in zip(starts, ends, labels):
        if s >= e:
            continue
        segs.append((s, e, label, text[s:e]))
    return segs


def _is_article(label: str) -> bool:
    return label.lower().startswith("article")


def _merge_small(
    segs: list[tuple[int, int, str, str]],
    min_t: float,
    max_t: float,
) -> list[tuple[int, int, str, str]]:
    """Greedy merge of consecutive *non-article* segments until >= min_t.

    Article segments are never merged into anything else — the article boundary
    is the primary structural split (§5.3) and collapsing it would break
    article-level citation. Small articles are emitted standalone (then
    window-split only if they exceed the ceiling). Preamble / recital segments
    are merged freely, retaining the first segment's label.
    """
    if not segs:
        return []
    merged: list[tuple[int, int, str, str]] = []
    cur = list(segs[0])
    for s, e, label, body in segs[1:]:
        cur_s, _cur_e, cur_label, cur_body = cur
        combined = cur_body + "\n" + body
        cannot_merge = _is_article(cur_label) or _is_article(label)
        if cannot_merge or _tokens(cur_body) >= min_t or _tokens(combined) > max_t:
            merged.append(tuple(cur))  # type: ignore[arg-type]
            cur = [s, e, label, body]
        else:
            cur = [cur_s, e, cur_label, combined]
    merged.append(tuple(cur))  # type: ignore[arg-type]
    return merged


def _snap_to_line(text: str, idx: int, *, prefer_backward: bool = True) -> int:
    """Move ``idx`` to the nearest newline so windows don't cut mid-line."""
    if idx <= 0 or idx >= len(text):
        return idx
    target = text.rfind("\n", 0, idx) if prefer_backward else text.find("\n", idx)
    if target == -1:
        return idx
    return target + 1 if prefer_backward else target


def _window_split(
    seg: tuple[int, int, str, str],
    max_t: float,
    overlap_r: float,
) -> list[tuple[int, int, str, str]]:
    """Split an over-long segment into overlapping windows, snapped to lines."""
    start, end, label, body = seg
    max_chars = max(1, int(max_t * config.CHARS_PER_TOKEN))
    if len(body) <= max_chars:
        return [seg]
    overlap_chars = int(max_chars * overlap_r)

    out: list[tuple[int, int, str, str]] = []
    i = 0
    while i < len(body):
        j = min(len(body), i + max_chars)
        # snap the end back to a newline unless we're already at the tail
        if j < len(body):
            j_snap = _snap_to_line(body, j, prefer_backward=True)
            if j_snap > i:
                j = j_snap
        sub = body[i:j]
        out.append((start + i, start + j, label if label != "Preamble" else "window", sub))
        if j >= len(body):
            break
        # step forward, but keep at least one char of progress
        next_i = j - overlap_chars
        if next_i <= i:
            next_i = i + 1
        i = next_i
    return out


def chunk_act(text: str, celex: str) -> list[Chunk]:
    """Chunk one act's cleaned text into `Chunk`s.

    Returns ``[]`` for empty input.
    """
    if not text or not text.strip():
        return []
    min_t = float(config.CHUNK_MIN_TOKENS)
    max_t = float(config.CHUNK_MAX_TOKENS)
    overlap_r = config.CHUNK_OVERLAP_RATIO

    segs = _segments(text)
    segs = _merge_small(segs, min_t, max_t)
    final: list[tuple[int, int, str, str]] = []
    for seg in segs:
        final.extend(_window_split(seg, max_t, overlap_r))

    chunks: list[Chunk] = []
    for idx, (s, e, label, body) in enumerate(final):
        body = body.strip("\n")
        if not body:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{celex}#{idx:04d}",
                celex=celex,
                chunk_index=idx,
                chunk_text=body,
                char_offset_start=s,
                char_offset_end=e,
                boundary=label,
            )
        )
    return chunks
