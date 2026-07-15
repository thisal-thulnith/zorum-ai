import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import TenantBase


class User(TenantBase):
    __tablename__ = "users"
    # Same email can exist at two different companies, but only once per company.
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    email: Mapped[str]
    password_hash: Mapped[str]  # argon2 hash — the real password is never stored
    full_name: Mapped[str]
    status: Mapped[str] = mapped_column(default="active", server_default="active")


class Role(TenantBase):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    key: Mapped[str]                      # "owner", "approver", ...
    name: Mapped[str]
    permissions: Mapped[list] = mapped_column(JSONB, default=list)


class UserRole(TenantBase):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))


class RefreshToken(TenantBase):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(unique=True)  # sha256 of the token
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]


class Invitation(TenantBase):
    __tablename__ = "invitations"

    email: Mapped[str]
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
