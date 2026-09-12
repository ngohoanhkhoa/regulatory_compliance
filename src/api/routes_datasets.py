"""Dataset registry routes: list, inspect, import/export, remove, acts.

- Every authenticated user sees all global regulatory datasets (read-only) plus
  their own private documents dataset.
- Admins import/remove regulatory datasets (whole dataset, via a bundle file).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from src import config
from src.api.schemas import (
    DatasetActsResponse,
    DatasetImportResult,
    DatasetItem,
    DatasetOut,
)
from src.auth import models
from src.auth.dependencies import get_current_admin, get_current_user
from src.corpus import manager as corpus_manager
from src.datasets import bundle, registry

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _can_view(dataset: dict, user: dict) -> bool:
    owner = dataset.get("owner_user_id")
    return owner is None or int(owner) == int(user["id"])


def _get_or_404(conn, dataset_id: int) -> dict:
    dataset = models.get_dataset(conn, dataset_id)
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    return dataset


@router.get("", response_model=list[DatasetOut])
def list_datasets(user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        models.ensure_user_documents_dataset(conn, user["id"])
        return [
            registry.serialize(conn, d)
            for d in models.list_datasets_visible(conn, user["id"])
        ]
    finally:
        conn.close()


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int, user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        dataset = _get_or_404(conn, dataset_id)
        if not _can_view(dataset, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        return registry.serialize(conn, dataset)
    finally:
        conn.close()


@router.get("/{dataset_id}/acts", response_model=DatasetActsResponse)
def dataset_acts(
    dataset_id: int,
    query: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None),
    order: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    conn = models.get_db()
    try:
        dataset = _get_or_404(conn, dataset_id)
        if not _can_view(dataset, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        if dataset.get("kind") != "regulatory":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Only regulatory datasets have acts"
            )
        path = registry.chunks_path_of(dataset)
    finally:
        conn.close()
    return corpus_manager.list_acts(
        path, query, limit=limit, offset=offset, sort=sort, order=order
    )


@router.get("/{dataset_id}/items/{item_id}", response_model=DatasetItem)
def dataset_item(
    dataset_id: int,
    item_id: str,
    user: dict = Depends(get_current_user),
):
    conn = models.get_db()
    try:
        dataset = _get_or_404(conn, dataset_id)
        if not _can_view(dataset, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        if dataset.get("kind") != "regulatory":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Only regulatory datasets have items"
            )
        path = registry.chunks_path_of(dataset)
    finally:
        conn.close()
    try:
        return corpus_manager.get_item(path, item_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} not found")
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Dataset chunks file is missing"
        )


@router.post(
    "/import", response_model=DatasetImportResult, status_code=status.HTTP_201_CREATED
)
async def import_dataset(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_admin),
):
    data = await file.read()
    conn = models.get_db()
    try:
        try:
            dataset = bundle.import_regulatory_dataset(
                conn, filename=file.filename or "dataset.zip", data=data
            )
        except bundle.DatasetBundleError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
        corpus_manager.clear_cache()
        return DatasetImportResult(
            status="ok", dataset=registry.serialize(conn, dataset)
        )
    finally:
        conn.close()


@router.get("/{dataset_id}/export")
def export_dataset(
    dataset_id: int,
    include_embeddings: bool = Query(default=True),
    user: dict = Depends(get_current_user),
):
    conn = models.get_db()
    try:
        dataset = _get_or_404(conn, dataset_id)
        if not _can_view(dataset, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        if dataset.get("kind") == "regulatory" and not user.get("is_admin"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Only admins can export regulatory datasets"
            )
        try:
            filename, payload = bundle.export_dataset(
                dataset, include_embeddings=include_embeddings
            )
        except bundle.DatasetBundleError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    finally:
        conn.close()
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: int, user: dict = Depends(get_current_admin)):
    conn = models.get_db()
    try:
        dataset = _get_or_404(conn, dataset_id)
        if dataset.get("kind") == "documents":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Manage individual documents instead of deleting your library.",
            )
        path = registry.chunks_path_of(dataset)
        _purge_dataset(dataset)
        models.delete_dataset(conn, dataset_id)
        corpus_manager.clear_cache(path)
        return {"id": dataset_id, "status": "deleted"}
    finally:
        conn.close()


def _purge_dataset(dataset: dict) -> None:
    """Remove a regulatory dataset's vector collection and imported files."""
    collection = registry.collection_of(dataset)
    if collection:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(config.VECTOR_STORE_DIR))
            client.delete_collection(collection)
        except Exception:
            pass

    path = registry.chunks_path_of(dataset)
    if path and dataset.get("source") == "import":
        try:
            parent = Path(path).resolve().parent
            if config.DATASETS_DIR.resolve() in parent.parents:
                shutil.rmtree(parent, ignore_errors=True)
        except OSError:
            pass
