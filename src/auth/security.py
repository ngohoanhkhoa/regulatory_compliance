"""Password hashing + JWT issue/verify (§6).

Uses ``bcrypt`` directly (avoids passlib's version-detection issues with
bcrypt 4.x) and ``PyJWT`` (HS256) for stateless sessions. The JWT secret,
algorithm, and TTL come from config (`.env`).
"""

from __future__ import annotations

import time
from typing import Any

import bcrypt
import jwt

from src import config


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Truncates to 72 bytes (bcrypt limit)."""
    pw_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    subject: str | int, *, extra: dict[str, Any] | None = None
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + config.JWT_TTL_MIN * 60,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALG)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` on bad/expired tokens."""
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALG])
