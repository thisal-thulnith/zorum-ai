import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import TenantBase


class AuditLog(TenantBase):
    """Append-only trail of every action by users, agents, or the system.

    The runtime DB role has no UPDATE/DELETE grant on this table (see RLS
    migration), so history cannot be rewritten — a compliance requirement
    for a platform whose agents touch financial records.
    """

    __tablename__ = "audit_log"

    occurred_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    actor_type: Mapped[str]                 # "user" | "agent" | "system"
    actor_id: Mapped[uuid.UUID | None]
    module_key: Mapped[str | None]
    action: Mapped[str]                     # "module.install", "invoice.approve", ...
    entity_type: Mapped[str | None]
    entity_id: Mapped[uuid.UUID | None]
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    autonomy_level: Mapped[int | None]
