from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TenantBase


class Module(Base):
    """Global catalog of installable modules (finance, inventory, ...). Shared by all tenants."""

    __tablename__ = "modules"

    key: Mapped[str] = mapped_column(primary_key=True)   # "finance"
    name: Mapped[str]
    version: Mapped[str]
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict)


class TenantModule(TenantBase):
    """One tenant's installation of one module — carries the autonomy governance switch."""

    __tablename__ = "tenant_modules"
    __table_args__ = (UniqueConstraint("tenant_id", "module_key"),)

    module_key: Mapped[str] = mapped_column(ForeignKey("modules.key"))
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # L1 suggest-only .. L4 fully autonomous. The policy engine reads THIS value.
    autonomy_level: Mapped[int] = mapped_column(default=1, server_default="1")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    paused: Mapped[bool] = mapped_column(default=False, server_default=text("false"))  # kill switch
