"""Topic CRUD + timeline routes.

A *topic* is a user-owned saved search. ``GET /topics/{id}/timeline`` runs the
saved query through the hybrid retriever and returns one entry per matching act,
ordered by document date so the UI can show how regulation evolved over time.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    TopicCreate,
    TopicOut,
    TopicTimelineItem,
    TopicTimelineResponse,
    TopicUpdate,
)
from src.auth import models
from src.auth.dependencies import get_current_user
from src.topics import service as topic_service

router = APIRouter(prefix="/api/topics", tags=["topics"])

_OUT_FIELDS = (
    "id",
    "name",
    "description",
    "search_query",
    "filters",
    "include_repealed",
    "created_at",
    "updated_at",
)


def _to_out(topic: dict[str, Any]) -> TopicOut:
    return TopicOut(**{k: topic.get(k) for k in _OUT_FIELDS})


def _filters_to_dict(filters: Any) -> dict[str, Any] | None:
    if filters is None:
        return None
    d = filters.model_dump(exclude_none=True)
    return d or None


@router.get("", response_model=list[TopicOut])
def list_topics(user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        return [_to_out(t) for t in models.list_topics(conn, user["id"])]
    finally:
        conn.close()


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def create_topic(req: TopicCreate, user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        tid = models.create_topic(
            conn,
            user_id=user["id"],
            name=req.name,
            description=req.description,
            # Empty means "derive from name + description" at query time.
            search_query=(req.search_query or "").strip(),
            filters=_filters_to_dict(req.filters),
            include_repealed=req.include_repealed,
        )
        topic = models.get_topic(conn, user["id"], tid)
    finally:
        conn.close()
    assert topic is not None
    return _to_out(topic)


@router.get("/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: int, user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        topic = models.get_topic(conn, user["id"], topic_id)
    finally:
        conn.close()
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return _to_out(topic)


@router.put("/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int,
    req: TopicUpdate,
    user: dict = Depends(get_current_user),
):
    conn = models.get_db()
    try:
        if models.get_topic(conn, user["id"], topic_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
        provided = req.model_dump(exclude_unset=True)
        kwargs: dict[str, Any] = {}
        for key in ("name", "description", "search_query", "include_repealed"):
            if key in provided:
                kwargs[key] = provided[key]
        if "filters" in provided:
            # Explicit filters (even empty) replace; ``{}`` clears them.
            kwargs["filters"] = _filters_to_dict(req.filters) or {}
        models.update_topic(conn, user["id"], topic_id, **kwargs)
        topic = models.get_topic(conn, user["id"], topic_id)
    finally:
        conn.close()
    assert topic is not None
    return _to_out(topic)


@router.delete("/{topic_id}", status_code=status.HTTP_200_OK)
def delete_topic(topic_id: int, user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        deleted = models.delete_topic(conn, user["id"], topic_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return {"id": topic_id, "status": "deleted"}


_ITEM_OUT_FIELDS = (
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


def _timeline_response(
    topic: dict[str, Any],
    items: list[dict[str, Any]],
    refreshed_at: float | None,
) -> TopicTimelineResponse:
    out_items: list[TopicTimelineItem] = []
    for item in items:
        data = {k: (item.get(k) or "") for k in _ITEM_OUT_FIELDS}
        data["score"] = float(item.get("score") or 0.0)
        out_items.append(TopicTimelineItem(**data))
    return TopicTimelineResponse(
        topic=_to_out(topic),
        items=out_items,
        count=len(out_items),
        generated_at=float(refreshed_at) if refreshed_at is not None else time.time(),
    )


@router.get("/{topic_id}/timeline", response_model=TopicTimelineResponse)
def topic_timeline(topic_id: int, user: dict = Depends(get_current_user)):
    """Return the stored timeline; research once on the first ever open."""
    conn = models.get_db()
    try:
        topic = models.get_topic(conn, user["id"], topic_id)
        if topic is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
        refreshed_at = models.get_topic_timeline_refreshed_at(conn, topic_id)
        if refreshed_at is None:
            items = topic_service.refresh_topic_timeline(topic)
            refreshed_at = models.replace_topic_timeline(conn, topic_id, items)
        else:
            items = models.get_topic_timeline(conn, topic_id)
    finally:
        conn.close()
    return _timeline_response(topic, items, refreshed_at)


@router.post("/{topic_id}/refresh", response_model=TopicTimelineResponse)
def refresh_topic(topic_id: int, user: dict = Depends(get_current_user)):
    """Re-run research and replace the stored timeline for this topic."""
    conn = models.get_db()
    try:
        topic = models.get_topic(conn, user["id"], topic_id)
        if topic is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
        previous_items = models.get_topic_timeline(conn, topic_id)
        items = topic_service.refresh_topic_timeline(
            topic, previous_items=previous_items
        )
        refreshed_at = models.replace_topic_timeline(conn, topic_id, items)
    finally:
        conn.close()
    return _timeline_response(topic, items, refreshed_at)
