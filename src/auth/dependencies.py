"""FastAPI auth dependencies: OAuth2 password bearer + get_current_user (§6).

The bcrypt context correctly recognises passlib's old-style ``$2b$`` hashes
that Python's own ``bcrypt`` library also produces, so the two are
interchangeable at the store layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.auth import models, security

# tokenUrl is the relative path clients use to obtain a token — must match the
# auth router's /auth/login route.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def _user_id_from_token(token: str | None) -> int:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    from jwt import PyJWTError

    try:
        payload = security.decode_access_token(token)
    except PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token subject")


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> dict[str, Any]:
    uid = _user_id_from_token(token)
    conn = models.get_db()
    try:
        user = models.get_user_by_id(conn, uid)
    finally:
        conn.close()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user
