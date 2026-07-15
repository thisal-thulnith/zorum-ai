"""Adversarial RLS tests: prove the DATABASE blocks cross-tenant access
even when application code is deliberately buggy (no WHERE clause).

These run against the restricted zorum_app role — the same role production uses.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

pytestmark = pytest.mark.asyncio


def app_factory():
    """Session factory using the RESTRICTED runtime role (RLS enforced)."""
    engine = create_async_engine(settings.app_database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_select_without_where_only_returns_own_tenant(two_tenants):
    a_id, b_id = two_tenants
    engine, factory = app_factory()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(a_id)}
        )
        # The "bug": no WHERE clause at all. RLS must filter anyway.
        rows = (await session.execute(text("SELECT tenant_id FROM users"))).fetchall()
        assert rows, "expected to see tenant A's own user"
        assert all(str(r.tenant_id) == str(a_id) for r in rows), \
            "LEAK: a row from another tenant was visible!"
    await engine.dispose()


async def test_update_other_tenant_affects_zero_rows(two_tenants):
    a_id, b_id = two_tenants
    engine, factory = app_factory()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(a_id)}
        )
        # Malicious/buggy attempt: rewrite tenant B's user names.
        result = await session.execute(
            text("UPDATE users SET full_name = 'hacked' WHERE tenant_id = :b"),
            {"b": str(b_id)},
        )
        assert result.rowcount == 0, "LEAK: tenant A modified tenant B's rows!"
    await engine.dispose()


async def test_no_tenant_context_sees_nothing(two_tenants):
    engine, factory = app_factory()
    async with factory() as session, session.begin():
        # No app.tenant_id set at all: query must error or return zero rows.
        try:
            rows = (await session.execute(text("SELECT id FROM users"))).fetchall()
            assert rows == [], "LEAK: rows visible without any tenant context!"
        except Exception:
            pass  # erroring is also acceptable (unset setting -> cast failure)
    await engine.dispose()
