"""Request-scoped guards: identity, permissions, and the RLS-scoped DB session."""

import uuid
from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth.jwt import decode_access_token
from app.db import tenant_session

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    permissions: list[str]

    def can(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        tenant_id=uuid.UUID(payload["tid"]),
        permissions=payload.get("perms", []),
    )


def require_permission(permission: str):
    """Usage: Depends(require_permission("finance.write")) -> 403 if missing."""
    def guard(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {permission}")
        return current
    return guard


async def tenant_db(current: CurrentUser = Depends(get_current_user)):
    """RLS-scoped session for the authenticated tenant. THE standard DB dependency."""
    async for session in tenant_session(current.tenant_id):
        yield session
