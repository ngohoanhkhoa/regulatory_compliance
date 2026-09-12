"""BM25 keyword index over the chunk corpus (§5.4).

Uses `rank_bm25` (lightweight, no extra service — §6). The index is built
in-process from the M1 chunk parquet the first time a `KeywordIndex` is
constructed; for a handful of users this is fast enough (a few seconds on
~150k chunks) that we don't bother persisting it between runs. A real FTS5
on-disk index is a documented later option if rebuild cost bites.

Tokenisation is purposefully simple: lowercase, split on non-alphanumeric,
keep tokens of length >= 2. This is enough to match exact legal citations
and defined terms (the whole point of carrying BM25 alongside dense vectors,
§5.4). Tokeniser is its own function so it's trivially testable.

Metadata pre-filtering (§5.4) is done as a *post*-filter because rank_bm25
has no native where-clause: we over-fetch, then drop rows that violate the
filter, keeping the per-keyword ranking intact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from src import config

# Over-fetch factor applied to BM25 n_results before post-filtering, so that
# dropping non-matching rows (e.g. repealed acts) still leaves enough hits.
_OVERFETCH = 3

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_STOPWORDS = frozenset(
    "a an the of to in on and or for is are be this that with as by at from it its "
    "shall may which has had have not no".split()
)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass
class KeywordHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }


class KeywordIndex:
    """In-memory BM25 over `chunk_id -> (text, metadata)`."""

    def __init__(self, chunks_path: Path = config.PROCESSED_CHUNKS_PATH) -> None:
        if not chunks_path.exists():
            raise FileNotFoundError(
                f"chunks parquet not found at {chunks_path}. Run M1 ingestion first."
            )
        from rank_bm25 import BM25Okapi

        df = pl.read_parquet(chunks_path)
        self._ids: list[str] = [str(x) for x in df["chunk_id"].to_list()]
        self._texts: list[str] = [(t or "") for t in df["chunk_text"].to_list()]
        self._metas: list[dict[str, Any]] = []
        for r in df.to_dicts():
            meta = {}
            for f in (
                "celex", "chunk_index", "boundary", "status", "date_document",
                "temporal_status", "eurovoc", "subject_matter", "eurlex_link",
                "act_name",
            ):
                v = r.get(f)
                meta[f] = "" if v is None else str(v)
            self._metas.append(meta)
        self._corpus_tokens = [tokenize(t) for t in self._texts]
        self._bm25 = BM25Okapi(self._corpus_tokens)
        self._id_to_pos = {cid: i for i, cid in enumerate(self._ids)}

    @property
    def count(self) -> int:
        return len(self._ids)

    def query(
        self,
        question: str,
        *,
        n_results: int = config.DEFAULT_TOP_K,
        filters: dict[str, Any] | None = None,
        include_repealed: bool = False,
    ) -> list[KeywordHit]:
        if not question.strip() or not self._ids:
            return []
        scores = self._bm25.get_scores(tokenize(question))
        # top by score
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        want = n_results * _OVERFETCH

        effective_filters = dict(filters or {})
        if not include_repealed:
            effective_filters["status"] = "In Force"

        hits: list[KeywordHit] = []
        for i in order:
            if scores[i] <= 0:
                break
            meta = self._metas[i]
            if not _passes(meta, effective_filters):
                continue
            hits.append(
                KeywordHit(
                    chunk_id=self._ids[i],
                    score=float(scores[i]),
                    text=self._texts[i],
                    metadata=meta,
                )
            )
            if len(hits) >= want:
                break
        return hits[:max(n_results, 0)]


def _passes(meta: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        value = meta.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and value not in expected["$in"]:
                return False
            if "$ne" in expected and value == expected["$ne"]:
                return False
        elif expected is None:
            if value not in (None, ""):
                return False
        elif value != expected:
            return False
    return True
