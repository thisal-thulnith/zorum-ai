"""Seed global data (module catalog) and per-tenant defaults (roles).

Run global seed manually:  uv run python -m app.seed
seed_roles(session, tenant_id) is called by signup for each new tenant.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.auth.models import Role
from app.core.modules.models import Module

FINANCE_MANIFEST = {
    "key": "finance",
    "emits": ["finance.document.uploaded", "finance.invoice.extracted", "finance.invoice.reviewed"],
    "subscribes": ["finance.document.uploaded"],
    "default_autonomy": 1,
}

DEFAULT_ROLES: list[dict] = [
    {"key": "owner", "name": "Owner", "permissions": ["*"]},
    {"key": "admin", "name": "Administrator",
     "permissions": ["users.manage", "modules.manage", "finance.read", "finance.write",
                     "approvals.decide", "audit.read"]},
    {"key": "finance_manager", "name": "Finance Manager",
     "permissions": ["finance.read", "finance.write", "approvals.decide", "audit.read"]},
    {"key": "approver", "name": "Approver", "permissions": ["finance.read", "approvals.decide"]},
    {"key": "viewer", "name": "Viewer", "permissions": ["finance.read"]},
]


async def seed_roles(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Create the default role set for a new tenant. Called by signup."""
    for spec in DEFAULT_ROLES:
        session.add(Role(tenant_id=tenant_id, **spec))


async def seed_global() -> None:
    """Upsert the module catalog. Uses the admin engine (modules is a global table)."""
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        existing = await session.get(Module, "finance")
        if existing is None:
            session.add(Module(key="finance", name="Finance & Accounting",
                               version="0.1.0", manifest=FINANCE_MANIFEST))
        else:
            existing.manifest = FINANCE_MANIFEST
    await engine.dispose()
    print("seeded: modules[finance]")


if __name__ == "__main__":
    asyncio.run(seed_global())
