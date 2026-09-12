"""Citation formatting + grounding guardrail (§5.5, §9.5, §10).

Citations: the LLM is instructed to inline-cite as ``[Act_name, CELEX, link]``
and to list each distinct cited act once under ``Sources:``. This module
provides:

- ``extract_celex_numbers(text)`` — find every CELEX number referenced in a
  free-text answer (handles ``32016R0679``, ``Regulation (EU) 2016/679``,
  ``EU 2016/679``, ``No 98/2013`` etc.).
- ``build_sources(retrieved_chunks)`` — the deterministic, de-duplicated source
  list attached to the ``/query`` response (§8) regardless of what the model
  wrote, so the UI source panel is always correct.
- ``check_grounding(answer, retrieved_celex)`` — the §9.5 / §10 grounding
  guardrail: every CELEX number in the answer must exist in the retrieved
  context set. Mismatches are returned as ``ungrounded`` CELEX ids so the API
  can flag the answer rather than silently trusting it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# CELEX ids in the CEPS dataset look like 32016R0679, 31987L0362, 32013R0098:
# sector digit(s) + 4-digit year + 1-letter type + 4-digit serial.
# In answers, acts are cited either canonically ("32016R0679") or in prose.
# EU citation conventions are inconsistent: "(EU) 2016/679" is year/serial,
# but "(EC) No 98/2013" is serial/year (the "No" keyword marks the number).
# We normalise *all* forms to the key "YYYYR<serial4>" (year + type letter +
# 4-digit serial) so a prose reference matches the canonical context id
# regardless of the leading sector digit. Type letter defaults to R for prose
# (regulations dominate the corpus); a wrong guess just means no false pass.
_CELEX_CANONICAL_RE = re.compile(r"\b(\d+)([RLHD])(\d{4})\b")
# "(EU|EC) No 98/2013"  -> serial=98, year=2013 ("No" marks the number first)
_NO_YEAR_RE = re.compile(r"\b(?:EU|EC)\)?\s*No\.?\s*(\d{1,4})/(\d{4})\b")
# "(EU) 2016/679"  -> year=2016, serial=679 (4-digit year first, no "No")
_YEAR_SERIAL_RE = re.compile(r"\b(?:EU|EC)\)?\s*(\d{4})/(\d{1,4})\b")


def _normalise(year: str, type_letter: str, serial: str) -> str:
    return f"{year.zfill(4)}{type_letter}{serial.zfill(4)}"


def extract_celex_numbers(text: str) -> list[str]:
    """Return normalised CELEX keys found in ``text`` (de-duplicated, order kept).

    Each key is ``YYYYR<serial>`` (or L/H/D) so canonical and prose citations
    of the same act compare equal — see module docstring.
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    for m in _CELEX_CANONICAL_RE.finditer(text):
        leading = m.group(1)
        year = leading[-4:] if len(leading) >= 4 else leading.zfill(4)
        cid = _normalise(year, m.group(2), m.group(3))
        if cid not in seen:
            seen.add(cid)
            found.append(cid)

    # "(EC) No 98/2013"  -> serial=98, year=2013
    for m in _NO_YEAR_RE.finditer(text):
        serial, year = m.group(1), m.group(2)
        cid = _normalise(year, "R", serial)
        if cid not in seen:
            seen.add(cid)
            found.append(cid)

    # "(EU) 2016/679"  -> year=2016, serial=679
    for m in _YEAR_SERIAL_RE.finditer(text):
        year, serial = m.group(1), m.group(2)
        cid = _normalise(year, "R", serial)
        if cid not in seen:
            seen.add(cid)
            found.append(cid)
    return found


def _normalise_context_celex(celex: str) -> str:
    """Normalise a canonical context CELEX to the same key shape as above."""
    m = _CELEX_CANONICAL_RE.search(celex or "")
    if not m:
        return (celex or "").strip()
    leading = m.group(1)
    year = leading[-4:] if len(leading) >= 4 else leading.zfill(4)
    return _normalise(year, m.group(2), m.group(3))


def _dataset_id(meta: dict) -> int | None:
    raw = meta.get("dataset_id")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_sources(retrieved_chunks: list[dict]) -> list[dict]:
    """Build the de-duplicated source list for the /query response (§8).

    Regulatory chunks are de-duplicated by CELEX; document chunks by
    (dataset, filename). Order = first appearance (rerank order).
    """
    out: list[dict] = []
    seen: set[str] = set()
    for c in retrieved_chunks:
        meta = c.get("metadata") or {}
        celex = str(meta.get("celex") or "").strip()
        filename = str(meta.get("filename") or "").strip()
        dataset_id = _dataset_id(meta)
        if celex:
            key = f"celex:{celex}"
        elif filename:
            key = f"doc:{dataset_id}:{filename}"
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "celex": celex,
                "act_name": meta.get("act_name", ""),
                "status": meta.get("status", ""),
                "link": meta.get("eurlex_link", ""),
                "chunk_excerpt": (c.get("text") or "")[:240],
                "dataset_id": dataset_id,
                "dataset_name": str(meta.get("dataset_name") or ""),
                "filename": filename,
            }
        )
    return out


@dataclass
class GroundingResult:
    grounded: bool
    ungrounded: list[str]  # CELEX ids in the answer not present in the context
    answer_celex: list[str]
    context_celex: list[str]


def check_grounding(
    answer: str, retrieved_chunks: list[dict]
) -> GroundingResult:
    answer_celex = extract_celex_numbers(answer)
    context_celex: list[str] = []
    context_keys: set[str] = set()
    for c in retrieved_chunks:
        celex = str((c.get("metadata") or {}).get("celex") or "").strip()
        if not celex:
            continue
        key = _normalise_context_celex(celex)
        if key not in context_keys:
            context_keys.add(key)
            context_celex.append(celex)
    ungrounded = [c for c in answer_celex if c not in context_keys]
    return GroundingResult(
        grounded=(len(ungrounded) == 0),
        ungrounded=ungrounded,
        answer_celex=answer_celex,
        context_celex=context_celex,
    )
