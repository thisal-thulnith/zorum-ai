"""rls policies — tenant isolation enforced by the database itself.

Creates the restricted runtime role `zorum_app` and applies a row-level
security policy to every tenant table. The app sets `app.tenant_id` per
transaction (see app/db.py tenant_session); Postgres then filters every
read and rejects every write outside that tenant, even if application
code is buggy. Superusers bypass RLS — which is why the app must never
connect as one.

Revision ID: c2313a51a594
Revises: 519b0386084f
Create Date: 2026-07-16 03:29:41.287260

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c2313a51a594'
down_revision: Union[str, Sequence[str], None] = '519b0386084f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "users",
    "roles",
    "user_roles",
    "refresh_tokens",
    "invitations",
    "tenant_modules",
    "audit_log",
]


def upgrade() -> None:
    # Dev password only — production sets a real one via env/secret manager.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'zorum_app') THEN "
        "CREATE ROLE zorum_app LOGIN PASSWORD 'zorum_app_dev'; "
        "END IF; END $$;"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO zorum_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zorum_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zorum_app"
    )
    # Audit log is append-only for the runtime role: history cannot be rewritten.
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM zorum_app")

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM zorum_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM zorum_app")
    op.execute("DROP ROLE IF EXISTS zorum_app")
