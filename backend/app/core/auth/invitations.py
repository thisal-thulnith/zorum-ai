"""Invite a teammate into YOUR tenant; they accept with a tokenized link.

Creating an invite runs under the RLS session (we know the tenant).
Accepting runs on the admin session (the invitee has no login yet).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.service import write_audit
from app.core.auth import emails
from app.core.auth.models import Invitation, Role, User, UserRole
from app.core.auth.passwords import hash_password
from app.core.tenancy.models import Tenant
from app.db import admin_session_factory

INVITE_DAYS = 7


async def create_invitation(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_id: uuid.UUID,
    email: str, role_key: str,
) -> None:
    role = (await session.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.key == role_key)
    )).scalar_one_or_none()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"role '{role_key}' not found")

    token = secrets.token_urlsafe(32)
    session.add(Invitation(
        tenant_id=tenant_id, email=email, role_id=role.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_DAYS),
    ))
    await write_audit(session, tenant_id=tenant_id, actor_type="user", actor_id=actor_id,
                      action="auth.invite", after={"email": email, "role": role_key})

    tenant = await session.get(Tenant, tenant_id)
    emails.send_invitation(email, token, tenant.name if tenant else "your team")


async def accept_invitation(req) -> str:
    """Create the invited user. Returns their email. Admin session: invitee has no auth yet."""
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    async with admin_session_factory() as session, session.begin():
        invite = (await session.execute(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )).scalar_one_or_none()
        now = datetime.now(UTC)
        if (invite is None or invite.accepted_at is not None
                or invite.expires_at < now):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired invitation")

        user = User(
            tenant_id=invite.tenant_id, email=invite.email,
            password_hash=hash_password(req.password), full_name=req.full_name,
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(tenant_id=invite.tenant_id, user_id=user.id, role_id=invite.role_id))
        invite.accepted_at = now

        await write_audit(session, tenant_id=invite.tenant_id, actor_type="user",
                          actor_id=user.id, action="auth.invite_accepted",
                          entity_type="user", entity_id=user.id)
        return invite.email
