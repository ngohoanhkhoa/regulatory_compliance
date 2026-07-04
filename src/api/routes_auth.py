"""Auth routes: /auth/register, /auth/login, /auth/me (§8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.schemas import Token, UserCreate, UserOut
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
            # The very first user becomes admin so /ingest is callable without manual SQL.
            is_admin=first_user,
        )
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
