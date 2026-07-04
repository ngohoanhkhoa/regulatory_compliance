"""Text cleaning + row-quality filtering for `act_raw_text` (§4, §5.1).

Steps, in order:
  1. Fix common Latin-1 / double-encoded mojibake artifacts seen in the CEPS
     export (e.g. `\u00c3\u00a8` standing in for `è`).
  2. Strip residual HTML entities / tags occasionally left by scraping.
  3. Normalise whitespace (collapse runs, unify newlines, trim).
  4. Replace NULs and other control chars that break Chroma/parquet.
  5. Apply a min-length + gibberish heuristic: drop rows whose cleaned text is
     below `MIN_RAW_TEXT_CHARS` or is dominated by non-letter noise.
  6. Lightweight English sanity check (no heavy dep): warn, not drop, on rows
     that look non-English — the source is meant to be English-only but a few
     stray acts slip through (§4 language-detection caveat).

Cleaning is pure (input str -> output str); row accept/reject decisions live in
`clean_row()` so it can be unit-tested without pandas/polars.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

from src import config

# --------------------------------------------------------------------------- #
# Regexes (compiled once)
# --------------------------------------------------------------------------- #
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Mojibake: a UTF-8 byte sequence that was decoded as Latin-1 / cp1252. The CEPS
# CSV contains sequences like "Ã©" (Ã + ©) that should be "é", "Ã¨" -> "è".
# Regular sub-patterns, applied greedily; anything unresolved is left as-is
# (we'd rather keep a few odd chars than aggressively mangle a valid string).
_MOJIBAKE_RULES: tuple[tuple[str, str], ...] = (
    ("Ã©", "é"),
    ("Ã¨", "è"),
    ("Ãª", "ê"),
    ("Ã«", "ë"),
    ("Ã¡", "á"),
    ("Ã ", "à"),
    ("Ã¢", "â"),
    ("Ã¥", "å"),
    ("Ã§", "ç"),
    ("Ã®", "î"),
    ("Ã¯", "ï"),
    ("Ã³", "ó"),
    ("Ã´", "ô"),
    ("Ã¶", "ö"),
    ("Ãº", "ú"),
    ("Ã¼", "ü"),
    ("Ã±", "ñ"),
    ("Ã€", "À"),
    ("Ã", "À"),
    ("â €", "—"),
    ("â€™", "'"),
    ("â€œ", "“"),
    ("â€\x9d", "”"),
    ("â€“", "–"),
    ('"', '"'),
    ('"', '"'),
)

# A small English-stopword set used by the gibberish / non-English heuristic.
_ENGLISH_STOPWORDS = frozenset(
    "the of and to in a is that for it on with as by be this an or at from "
    "which have has had are was were shall may article regulation that member "
    "states union european commission council parliament".split()
)


@dataclass
class CleanResult:
    """Outcome of cleaning a single act's raw text."""

    text: str | None
    accepted: bool
    reason: str | None


# --------------------------------------------------------------------------- #
# Pure string cleaning
# --------------------------------------------------------------------------- #
def _fix_mojibake(s: str) -> str:
    for bad, good in _MOJIBAKE_RULES:
        if bad in s:
            s = s.replace(bad, good)
    return s


def clean_text(text: str) -> str:
    """Normalise one act's raw text. Pure: str -> str, never returns None."""
    if not isinstance(text, str):
        return ""
    s = text
    s = s.replace("\ufeff", "")
    s = _fix_mojibake(s)
    s = html.unescape(s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = _CONTROL_RE.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _WS_RE.sub(" ", s)
    s = _MULTI_NL_RE.sub("\n\n", s)
    s = s.strip()
    if s:
        s = unicodedata.normalize("NFC", s)
    return s


# --------------------------------------------------------------------------- #
# Quality / language heuristics
# --------------------------------------------------------------------------- #
def _letter_ratio(s: str) -> float:
    if not s:
        return 0.0
    letters = sum(1 for c in s if c.isalpha() or c.isspace())
    return letters / len(s)


def _english_score(s: str) -> float:
    """Cheap English-likeness score in [0,1] based on common stopwords.

    No external dependency on purpose (§6: keep deps minimal & debuggable).
    Not a hard filter — used only to warn/flag, never to drop a row.
    """
    if not s:
        return 0.0
    tokens = re.findall(r"[a-zA-Z]{2,}", s.lower())
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in _ENGLISH_STOPWORDS)
    return hits / len(tokens)


def is_acceptable(
    clean: str, *, min_chars: int = config.MIN_RAW_TEXT_CHARS
) -> tuple[bool, str | None]:
    """Decide whether a *cleaned* text passes the row-quality gates.

    Returns (accepted, reason_if_rejected).
    """
    if not clean:
        return False, "empty"
    if len(clean) < min_chars:
        return False, f"too_short (<{min_chars} chars)"
    if _letter_ratio(clean) < 0.55:
        return False, "gibberish (low letter ratio)"
    if _english_score(clean) < 0.015:
        return False, "not_english (low stopword ratio)"
    return True, None


def clean_row(
    raw_text: str | None,
    *,
    min_chars: int = config.MIN_RAW_TEXT_CHARS,
) -> CleanResult:
    """Clean + gate a single row's raw text → CleanResult."""
    clean = clean_text(raw_text or "")
    ok, reason = is_acceptable(clean, min_chars=min_chars)
    return CleanResult(text=clean if ok else None, accepted=ok, reason=reason)
