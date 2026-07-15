"""Single entry point for writing audit rows. Everything notable calls this."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.models import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_type: str,               # "user" | "agent" | "system"
    action: str,                   # "auth.signup", "module.install", ...
    actor_id: uuid.UUID | None = None,
    module_key: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    autonomy_level: int | None = None,
) -> None:
    session.add(AuditLog(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        module_key=module_key,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        autonomy_level=autonomy_level,
    ))
