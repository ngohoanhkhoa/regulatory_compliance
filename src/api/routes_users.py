"""Admin user-management routes (/api/admin/users).

Admins can list, create, rename, reset the password of, grant/revoke admin on,
and hard-delete users. Safety guards prevent removing your own admin rights or
deleting yourself / the last remaining admin.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    AdminFlagUpdate,
    AdminPasswordReset,
    AdminUserCreate,
    AdminUsernameUpdate,
    AdminUserOut,
)
from src.auth import models, security
from src.auth.dependencies import get_current_admin
from src.users import service as users_service

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _out(user: dict[str, Any]) -> AdminUserOut:
    return AdminUserOut(
        id=int(user["id"]),
        username=user["username"],
        is_admin=bool(user["is_admin"]),
        created_at=user.get("created_at"),
    )


def _get_or_404(conn, user_id: int) -> dict[str, Any]:
    user = models.get_user_by_id(conn, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.get("", response_model=list[AdminUserOut])
def list_users(admin: dict = Depends(get_current_admin)):
    conn = models.get_db()
    try:
        return [_out(u) for u in models.list_users(conn)]
    finally:
        conn.close()


@router.post("", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: AdminUserCreate, admin: dict = Depends(get_current_admin)):
    username = payload.username.strip()
    conn = models.get_db()
    try:
        if models.get_user_by_name(conn, username) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
        uid = models.create_user(
            conn,
            username=username,
            hashed_password=security.hash_password(payload.password),
            is_admin=payload.is_admin,
        )
        created = models.get_user_by_id(conn, uid)
        assert created is not None
        return _out(created)
    finally:
        conn.close()


@router.put("/{user_id}/username", response_model=AdminUserOut)
def rename_user(
    user_id: int,
    payload: AdminUsernameUpdate,
    admin: dict = Depends(get_current_admin),
):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "username: String should have at least 3 characters",
        )
    conn = models.get_db()
    try:
        _get_or_404(conn, user_id)
        existing = models.get_user_by_name(conn, username)
        if existing is not None and int(existing["id"]) != int(user_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
        models.update_username(conn, user_id, username)
        updated = models.get_user_by_id(conn, user_id)
        assert updated is not None
        return _out(updated)
    finally:
        conn.close()


@router.put("/{user_id}/password")
def reset_password(
    user_id: int,
    payload: AdminPasswordReset,
    admin: dict = Depends(get_current_admin),
):
    conn = models.get_db()
    try:
        _get_or_404(conn, user_id)
        models.update_password(
            conn, user_id, security.hash_password(payload.new_password)
        )
        return {"status": "ok", "user_id": user_id}
    finally:
        conn.close()


@router.put("/{user_id}/admin", response_model=AdminUserOut)
def set_admin(
    user_id: int,
    payload: AdminFlagUpdate,
    admin: dict = Depends(get_current_admin),
):
    conn = models.get_db()
    try:
        target = _get_or_404(conn, user_id)
        if not payload.is_admin and bool(target["is_admin"]):
            if int(user_id) == int(admin["id"]):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "You cannot remove your own admin rights",
                )
            if models.count_admins(conn) <= 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "Cannot remove the last admin"
                )
        models.set_admin(conn, user_id, payload.is_admin)
        updated = models.get_user_by_id(conn, user_id)
        assert updated is not None
        return _out(updated)
    finally:
        conn.close()


@router.delete("/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(get_current_admin)):
    conn = models.get_db()
    try:
        target = _get_or_404(conn, user_id)
        if int(user_id) == int(admin["id"]):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "You cannot delete your own account"
            )
        if bool(target["is_admin"]) and models.count_admins(conn) <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot delete the last admin"
            )
        result = users_service.delete_user_data(conn, user_id)
        return {"status": "deleted", **result}
    finally:
        conn.close()
