"""Access-token (JWT) issue/verify + refresh-token generation.

Access token: short-lived (15 min), signed with JWT_SECRET (HS256), carries
identity + permission snapshot. Verifying it is pure math — no DB hit.

Refresh token: long random string (30 days). We store only its sha256 in the
refresh_tokens table and ROTATE it on every use: each refresh revokes the old
token and issues a new one, so a stolen token dies the moment the real user
refreshes (the thief's copy stops working — and reuse is detectable).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt

from app.config import settings

ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 30
ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, permissions: list[str]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "perms": permissions,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises pyjwt exceptions (expired/invalid) — callers turn those into 401s."""
    payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise pyjwt.InvalidTokenError("not an access token")
    return payload


def new_refresh_token() -> tuple[str, str, datetime]:
    """Return (plaintext_token, sha256_hash, expires_at). Only the hash is stored."""
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_DAYS)
    return token, token_hash, expires_at


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
