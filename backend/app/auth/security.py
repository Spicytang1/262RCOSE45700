from __future__ import annotations

import hashlib
import secrets

import jwt

from app.config import Settings

JWT_ALGORITHM = "HS256"


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def encode_access_token(*, user_id: str, session_id: str, settings: Settings, issued_at: int, expires_at: int) -> str:
    payload = {"sub": user_id, "sid": session_id, "iat": issued_at, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, object] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return dict(payload)
