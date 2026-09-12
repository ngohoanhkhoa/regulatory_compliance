"""Auth routes: /auth/register, /auth/login, /auth/me (§8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.schemas import (
    PasswordUpdate,
    Token,
    UserCreate,
    UsernameUpdate,
    UserOut,
)
from src.auth import models, security
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate):
    conn = models.get_db()
    try:
        if models.get_user_by_name(conn, payload.username):
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
        first_user = models.list_users(conn) == []
        uid = models.create_user(
            conn,
            username=payload.username,
            hashed_password=security.hash_password(payload.password),
            # The very first user becomes admin so corpus admin is usable without manual SQL.
            is_admin=first_user,
        )
        models.ensure_user_documents_dataset(conn, uid)
        user = models.get_user_by_id(conn, uid)
        return UserOut(id=user["id"], username=user["username"], is_admin=bool(user["is_admin"]))
    finally:
        conn.close()


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    conn = models.get_db()
    try:
        user = models.get_user_by_name(conn, form.username)
        if not user or not security.verify_password(form.password, user["hashed_password"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
        token = security.create_access_token(
            user["id"], extra={"username": user["username"], "admin": bool(user["is_admin"])}
        )
        return Token(access_token=token)
    finally:
        conn.close()


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], username=user["username"], is_admin=bool(user["is_admin"]))


@router.put("/me/username", response_model=UserOut)
def update_my_username(payload: UsernameUpdate, user: dict = Depends(get_current_user)):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "username: String should have at least 3 characters",
        )
    conn = models.get_db()
    try:
        existing = models.get_user_by_name(conn, username)
        if existing is not None and int(existing["id"]) != int(user["id"]):
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
        models.update_username(conn, user["id"], username)
        return UserOut(id=user["id"], username=username, is_admin=bool(user["is_admin"]))
    finally:
        conn.close()


@router.put("/me/password")
def update_my_password(payload: PasswordUpdate, user: dict = Depends(get_current_user)):
    conn = models.get_db()
    try:
        fresh = models.get_user_by_id(conn, user["id"])
        if fresh is None or not security.verify_password(
            payload.current_password, fresh["hashed_password"]
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Current password is incorrect"
            )
        models.update_password(
            conn, user["id"], security.hash_password(payload.new_password)
        )
        return {"status": "ok"}
    finally:
        conn.close()
