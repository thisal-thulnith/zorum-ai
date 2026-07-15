"""Database engine, sessions, and declarative bases.

Two connection roles exist:
- settings.database_url      -> admin role (zorum): used by Alembic migrations only.
- settings.app_database_url  -> restricted role (zorum_app): used by the app at runtime.
  This role is subject to Row-Level Security, so a request can only ever see
  rows belonging to the tenant set via `SET LOCAL app.tenant_id`.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings

# Runtime engine — restricted role, RLS applies.
engine = create_async_engine(settings.app_database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base for global tables shared by all tenants (tenants, modules)."""


class TenantBase(Base):
    """Base for tenant-owned tables: guarantees id + tenant_id + created_at."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Yield a session scoped to one tenant for the duration of one transaction.

    set_config(..., is_local=true) applies only to the current transaction,
    so pooled connections can never leak one tenant's id into another request.
    """
    async with async_session_factory() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            yield session
