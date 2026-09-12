"""Personal document library routes (/api/documents)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.schemas import (
    DocumentOut,
    DocumentSearchRequest,
    DocumentSearchResult,
)
from src.auth import models
from src.auth.dependencies import get_current_user
from src.documents import extract, service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        return models.list_documents(conn, user["id"])
    finally:
        conn.close()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tags: str = Form(default=""),
    user: dict = Depends(get_current_user),
):
    data = await file.read()
    conn = models.get_db()
    try:
        try:
            return service.create_document(
                conn,
                user_id=user["id"],
                filename=file.filename or "upload",
                content_type=file.content_type or "",
                data=data,
                tags=tags,
            )
        except extract.UnsupportedDocument as exc:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc))
        except extract.DocumentExtractionError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    finally:
        conn.close()


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(document_id: int, user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        deleted = service.delete_document(conn, user["id"], document_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return {"id": document_id, "status": "deleted"}


@router.post("/search", response_model=list[DocumentSearchResult])
def search_documents(
    req: DocumentSearchRequest,
    user: dict = Depends(get_current_user),
):
    hits = service.search_documents(user["id"], req.query, top_k=req.top_k or 5)
    out: list[DocumentSearchResult] = []
    for h in hits:
        meta = h.get("metadata") or {}
        doc_id = meta.get("document_id")
        chunk_index = meta.get("chunk_index")
        out.append(
            DocumentSearchResult(
                chunk_id=str(h.get("chunk_id") or ""),
                score=float(h.get("score") or 0.0),
                text=str(h.get("text") or ""),
                document_id=int(doc_id) if doc_id is not None else None,
                filename=str(meta.get("filename") or ""),
                chunk_index=int(chunk_index) if chunk_index is not None else None,
            )
        )
    return out
