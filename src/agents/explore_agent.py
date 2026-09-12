"""Dataset Explorer Agent — answers exploration questions by querying the parquet store."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
import polars as pl

from src import config

EXPLORE_PROMPT = """\
You are a dataset explorer for the CEPS EurLex corpus (~140k EU legal acts, frozen Aug 2019). \
Given a user question about the dataset, return a JSON object specifying what data to retrieve.

Available columns: celex, act_name, status, subject_matter, eurovoc, authors, \
date_document, temporal_status, eurlex_link, boundary.

Important: "act_type" is NOT available — use general statistics or subject_matter instead. \
For GDPR, search for "2016/679" or "protection of personal data". \
For well-known regulations, use the CELEX number (e.g. "32016R0679" for GDPR).

Available operations and their JSON format:

1. COUNT unique acts matching filters:
   {{"op": "count", "filters": {{"column": "value", ...}}}}

2. COUNT per group (e.g. acts by status):
   {{"op": "group_count", "column": "status", "top_n": 10}}

3. LIST acts matching filters (returns up to top_n rows):
   {{"op": "list", "filters": {{"column": "value", ...}},
     "columns": ["celex", "act_name", ...], "top_n": 5}}

4. SEARCH by keyword in act_name or any column:
   {{"op": "search", "keyword": "gdpr", "columns": ["celex", "act_name", "status"], "top_n": 5}}

5. DESCRIBE a specific act by CELEX:
   {{"op": "describe", "celex": "32016R0679"}}

6. STATS (dataset overview):
   {{"op": "stats"}}

Only use filters for columns that actually exist. Return ONLY valid JSON, no commentary.

User question: {question}
JSON:"""


class ExploreAgent:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.base_url = (base_url or config.OPENROUTER_BASE_URL).rstrip("/")
        self.model = model or config.RERANKER_LLM_MODEL
        self._endpoint = f"{self.base_url}/chat/completions"

    def answer(self, question: str) -> dict[str, Any]:
        plan = self._plan(question)
        result = self._execute(plan)
        return {
            "answer": result,
            "sources": [],
            "warnings": [],
            "disclaimer": "",
            "grounded": True,
            "ungrounded_celex": [],
            "model": "explore-agent",
            "query_log_id": None,
            "intent": "explore",
        }

    def _plan(self, question: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        prompt = EXPLORE_PROMPT.format(question=question.strip()[:2000])
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 512,
        }

        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = httpx.post(self._endpoint, headers=headers, json=payload, timeout=30.0)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(1)
                continue

            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
                return {"op": "stats"}

            if resp.status_code == 429:
                time.sleep(2)
                continue

            last_exc = RuntimeError(f"explore plan failed ({resp.status_code}): {resp.text[:200]}")
            if attempt < 1:
                time.sleep(1)
                continue
            raise last_exc

        if last_exc:
            return {"op": "stats"}
        return {"op": "stats"}

    def _execute(self, plan: dict[str, Any]) -> str:
        op = plan.get("op", "stats")
        chunks_path = config.PROCESSED_CHUNKS_PATH

        if not chunks_path.exists():
            return (
                "The dataset is not available (chunks parquet not found). "
                "Please run ingestion first."
            )

        try:
            lf = pl.scan_parquet(chunks_path)
        except Exception as exc:
            return f"Could not read the dataset: {exc}"

        if op == "stats":
            return self._stats(lf)

        if op == "count":
            return self._count(lf, plan.get("filters", {}))

        if op == "group_count":
            return self._group_count(lf, plan.get("column", "status"), plan.get("top_n", 10))

        if op == "list":
            return self._list(lf, plan)

        if op == "search":
            return self._search(lf, plan)

        if op == "describe":
            return self._describe(lf, plan.get("celex", ""))

        return self._stats(lf)

    def _stats(self, lf: pl.LazyFrame) -> str:
        try:
            total_chunks = lf.select(pl.len()).collect().item()
            total_acts = lf.select(pl.col("celex").n_unique()).collect().item()
            statuses = (
                lf.group_by("status").agg(pl.len())
                .sort("len", descending=True)
                .collect()
            )
            types = (
                lf.group_by("act_type").agg(pl.len())
                .sort("len", descending=True)
                .head(10)
                .collect()
            )
            status_lines = "\n".join(
                f"  • {r['status']}: {r['len']} chunks" for r in statuses.iter_rows(named=True)
            )
            type_lines = "\n".join(
                f"  • {r['act_type'] or '(unknown)'}" for r in types.iter_rows(named=True)
            )
            return (
                f"📊 **CEPS EurLex Dataset Overview**\n\n"
                f"• Total legal acts: **{total_acts:,}**\n"
                f"• Total chunks: **{total_chunks:,}**\n"
                f"• Data cutoff: {config.DATA_CUTOFF_DATE}\n\n"
                f"**Distribution by status:**\n{status_lines}\n\n"
                f"**Most common act types (top 10):**\n{type_lines}"
            )
        except Exception as exc:
            return f"Could not compute stats: {exc}"

    def _count(self, lf: pl.LazyFrame, filters: dict[str, str]) -> str:
        for col, val in filters.items():
            col_name = col.lower().replace(" ", "_")
            lf = lf.filter(pl.col(col_name).str.contains(f"(?i){val}"))
        try:
            count = lf.select(pl.col("celex").n_unique()).collect().item()
            filter_desc = " and ".join(f"{k}={v}" for k, v in filters.items())
            suffix = f" filter: {filter_desc}" if filter_desc else ""
            return f"**{count:,}** distinct acts match{suffix}."
        except Exception as exc:
            return f"Could not count: {exc}"

    def _group_count(self, lf: pl.LazyFrame, column: str, top_n: int) -> str:
        try:
            result = (
                lf.group_by(column).agg(pl.col("celex").n_unique().alias("count"))
                .sort("count", descending=True)
                .head(top_n)
                .collect()
            )
            lines = "\n".join(
                f"  • **{r[column] or '(none)'}**: {r['count']:,} acts"
                for r in result.iter_rows(named=True)
            )
            return (
                f"**Acts by {column.replace('_', ' ')}** (top {top_n}):\n\n{lines}"
            )
        except Exception as exc:
            return f"Could not group by {column}: {exc}"

    def _list(self, lf: pl.LazyFrame, plan: dict[str, Any]) -> str:
        filters = plan.get("filters", {})
        columns = plan.get("columns", ["celex", "act_name", "status"])
        top_n = min(plan.get("top_n", 5), 10)

        for col, val in filters.items():
            col_name = col.lower().replace(" ", "_")
            lf = lf.filter(pl.col(col_name).str.contains(f"(?i){val}"))

        try:
            result = lf.select(columns).unique(subset=["celex"]).head(top_n).collect()
            if result.is_empty():
                return "No acts match the given filters."
            lines = "\n".join(
                f"  • **{r['celex']}** — {r.get('act_name', 'N/A')}"
                + (f" [{r.get('status', '')}]" if r.get('status') else "")
                for r in result.iter_rows(named=True)
            )
            return f"**Top matches:**\n\n{lines}"
        except Exception as exc:
            return f"Could not list acts: {exc}"

    def _search(self, lf: pl.LazyFrame, plan: dict[str, Any]) -> str:
        keyword = plan.get("keyword", "")
        columns = plan.get("columns", ["celex", "act_name", "status"])
        top_n = min(plan.get("top_n", 5), 10)

        if not keyword:
            return "Please provide a keyword to search for."

        try:
            lf = lf.filter(
                pl.col("act_name").str.contains(f"(?i){keyword}")
                | pl.col("subject_matter").str.contains(f"(?i){keyword}")
                | pl.col("eurovoc").str.contains(f"(?i){keyword}")
            )
            result = lf.select(columns).unique(subset=["celex"]).head(top_n).collect()
            if result.is_empty():
                return f"No acts match the keyword **{keyword}**."
            lines = "\n".join(
                f"  • **{r['celex']}** — {r.get('act_name', 'N/A')}"
                + (f" [{r.get('status', '')}]" if r.get('status') else "")
                for r in result.iter_rows(named=True)
            )
            return f"**Search results for \"{keyword}\":**\n\n{lines}"
        except Exception as exc:
            return f"Could not search: {exc}"

    def _describe(self, lf: pl.LazyFrame, celex: str) -> str:
        if not celex:
            return "Please provide a CELEX number."

        try:
            result = lf.filter(pl.col("celex") == celex).head(1).collect()
            if result.is_empty():
                return f"No act found with CELEX **{celex}**."

            row = next(result.iter_rows(named=True))

            full_text = self._fetch_full_text(celex)

            text_preview = ""
            if full_text:
                preview = full_text[:1500]
                text_preview = (
                    f"\n\n**Full text** (first 1500 chars):\n\n{preview}"
                    f"{'...' if len(full_text) > 1500 else ''}"
                )

            return (
                f"**{row.get('celex')}**\n\n"
                f"• Name: {row.get('act_name', 'N/A')}\n"
                f"• Status: {row.get('status', 'N/A')}\n"
                f"• Date: {row.get('date_document', 'N/A')}\n"
                f"• Temporal status: {row.get('temporal_status', 'N/A')}\n"
                f"• Subject matter: {row.get('subject_matter', 'N/A')}\n"
                f"• Authors: {row.get('authors', 'N/A')}\n"
                + (
                    f"• [View on EurLex]({row.get('eurlex_link', '')})\n"
                    if row.get("eurlex_link")
                    else ""
                )
                + f"{text_preview}"
            )
        except Exception as exc:
            return f"Could not describe act: {exc}"

    @staticmethod
    def _fetch_full_text(celex: str) -> str:
        csv_path = config.RAW_CSV_PATH
        if not csv_path.exists():
            return ""

        try:
            df = pl.scan_parquet(config.PROCESSED_CHUNKS_PATH).filter(
                pl.col("celex") == celex
            ).sort("chunk_index").collect()

            if df.is_empty():
                return ""

            return "\n\n".join(
                str(t) for t in df.get_column("chunk_text").to_list() if t
            )
        except Exception:
            return ""
        except Exception as exc:
            return f"Could not describe act: {exc}"


_explore_agent: ExploreAgent | None = None


def get_explore_agent() -> ExploreAgent:
    global _explore_agent
    if _explore_agent is None:
        _explore_agent = ExploreAgent()
    return _explore_agent
