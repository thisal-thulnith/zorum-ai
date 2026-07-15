"""Shared fixtures: two tenants with one user each, created via the ADMIN engine.

Setup uses the admin role (bypasses RLS) because creating cross-tenant fixtures
is exactly what the runtime role must never be able to do.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.auth.models import User
from app.core.tenancy.models import Tenant


@pytest.fixture(scope="session")
def admin_engine_url() -> str:
    return settings.database_url


@pytest_asyncio.fixture()
async def two_tenants():
    """Yield (tenant_a_id, tenant_b_id), each with one user. Cleans up after."""
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = uuid.uuid4().hex[:8]
    a_id, b_id = uuid.uuid4(), uuid.uuid4()

    async with factory() as session, session.begin():
        session.add_all([
            Tenant(id=a_id, name="Tenant A", slug=f"tenant-a-{run_id}"),
            Tenant(id=b_id, name="Tenant B", slug=f"tenant-b-{run_id}"),
            User(tenant_id=a_id, email=f"a-{run_id}@example.com",
                 password_hash="x", full_name="Alice A"),
            User(tenant_id=b_id, email=f"b-{run_id}@example.com",
                 password_hash="x", full_name="Bob B"),
        ])

    yield a_id, b_id

    async with factory() as session, session.begin():
        for model, ids in ((User, (a_id, b_id)), (Tenant, (a_id, b_id))):
            from sqlalchemy import delete
            await session.execute(delete(model).where(
                (model.tenant_id.in_(ids)) if model is User else (model.id.in_(ids))
            ))
    await engine.dispose()
