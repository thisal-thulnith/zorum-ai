"""Auth kernel: signup, login, token refresh, permission resolution.

This module is the ONLY feature code allowed to use admin_session_factory —
at signup the tenant doesn't exist yet, and at login we don't know which
tenant the email belongs to until we've found the user. Everything after
authentication runs under RLS via the restricted role.
"""

import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.service import write_audit
from app.core.auth import jwt as tokens
from app.core.auth.models import RefreshToken, Role, User, UserRole
from app.core.auth.passwords import hash_password, verify_password
from app.core.modules.models import TenantModule
from app.core.tenancy.models import Tenant
from app.db import admin_session_factory
from app.seed import seed_roles


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:6]}"  # suffix guarantees uniqueness


async def resolve_permissions(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await session.execute(
        select(Role.permissions)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    perms: set[str] = set()
    for (permissions,) in rows:
        perms.update(permissions or [])
    return sorted(perms)


async def _issue_token_pair(session: AsyncSession, user: User) -> tuple[str, str]:
    perms = await resolve_permissions(session, user.id)
    access = tokens.create_access_token(user.id, user.tenant_id, perms)
    refresh_plain, refresh_hash, expires_at = tokens.new_refresh_token()
    session.add(RefreshToken(
        tenant_id=user.tenant_id, user_id=user.id,
        token_hash=refresh_hash, expires_at=expires_at,
    ))
    return access, refresh_plain


async def signup(req) -> tuple[str, str]:
    """Create tenant + roles + owner + finance module install, atomically."""
    async with admin_session_factory() as session, session.begin():
        existing = await session.execute(select(User).where(User.email == req.email))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

        tenant = Tenant(name=req.company_name, slug=_slugify(req.company_name))
        session.add(tenant)
        await session.flush()  # materialize tenant.id for the rows below

        await seed_roles(session, tenant.id)
        await session.flush()

        owner_role = (await session.execute(
            select(Role).where(Role.tenant_id == tenant.id, Role.key == "owner")
        )).scalar_one()

        user = User(
            tenant_id=tenant.id, email=req.email,
            password_hash=hash_password(req.password), full_name=req.full_name,
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(tenant_id=tenant.id, user_id=user.id, role_id=owner_role.id))

        # Every new tenant starts with finance installed, L1 suggest-only.
        session.add(TenantModule(tenant_id=tenant.id, module_key="finance", autonomy_level=1))

        await write_audit(session, tenant_id=tenant.id, actor_type="user", actor_id=user.id,
                          action="auth.signup", entity_type="tenant", entity_id=tenant.id,
                          after={"company": req.company_name})

        return await _issue_token_pair(session, user)


async def login(req) -> tuple[str, str]:
    async with admin_session_factory() as session, session.begin():
        result = await session.execute(
            select(User).where(User.email == req.email, User.status == "active")
        )
        users = result.scalars().all()
        # Same email may exist at multiple tenants — the password picks the account.
        for user in users:
            if verify_password(req.password, user.password_hash):
                return await _issue_token_pair(session, user)
        # Uniform error: never reveal whether the email exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")


async def refresh(refresh_token: str) -> tuple[str, str]:
    """Rotate: verify -> revoke old -> issue new pair."""
    token_hash = tokens.hash_refresh_token(refresh_token)
    async with admin_session_factory() as session, session.begin():
        row = (await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )).scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None or row.revoked_at is not None or row.expires_at < now:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
        row.revoked_at = now
        user = (await session.execute(
            select(User).where(User.id == row.user_id, User.status == "active")
        )).scalar_one_or_none()
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user disabled")
        return await _issue_token_pair(session, user)


async def logout(refresh_token: str) -> None:
    token_hash = tokens.hash_refresh_token(refresh_token)
    async with admin_session_factory() as session, session.begin():
        row = (await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )).scalar_one_or_none()
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
