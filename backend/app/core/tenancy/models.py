import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tenant(Base):
    """A customer company. Global table — it has no tenant_id; it IS the tenant."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    industry: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="active", server_default="active")
    # New tenants start in shadow mode: agents suggest everything, execute nothing.
    shadow_mode: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
