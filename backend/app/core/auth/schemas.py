"""Request/response shapes for auth endpoints (Pydantic validates every field)."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    permissions: list[str]


class InviteRequest(BaseModel):
    email: EmailStr
    role_key: str


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
