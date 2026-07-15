"""End-to-end auth tests: real HTTP requests (in-process) against the real DB."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def signup_payload():
    run = uuid.uuid4().hex[:8]
    return {
        "company_name": f"Acme {run}",
        "email": f"owner-{run}@example.com",
        "password": "correct-horse-battery",
        "full_name": "Ada Owner",
    }


async def test_signup_login_me_roundtrip():
    payload = signup_payload()
    async with client() as c:
        r = await c.post("/api/v1/auth/signup", json=payload)
        assert r.status_code == 201, r.text
        tokens = r.json()
        assert tokens["access_token"] and tokens["refresh_token"]

        r = await c.post("/api/v1/auth/login",
                         json={"email": payload["email"], "password": payload["password"]})
        assert r.status_code == 200, r.text

        access = r.json()["access_token"]
        r = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["email"] == payload["email"]
        assert me["permissions"] == ["*"]  # signup makes you owner


async def test_wrong_password_rejected_uniformly():
    payload = signup_payload()
    async with client() as c:
        await c.post("/api/v1/auth/signup", json=payload)
        r = await c.post("/api/v1/auth/login",
                         json={"email": payload["email"], "password": "wrong-password-123"})
        assert r.status_code == 401
        r2 = await c.post("/api/v1/auth/login",
                          json={"email": "ghost@example.com", "password": "wrong-password-123"})
        # Same error whether the email exists or not — no account enumeration.
        assert r2.status_code == 401
        assert r.json() == r2.json()


async def test_refresh_rotates_and_old_token_dies():
    payload = signup_payload()
    async with client() as c:
        r = await c.post("/api/v1/auth/signup", json=payload)
        old_refresh = r.json()["refresh_token"]

        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 200, r.text
        new_refresh = r.json()["refresh_token"]
        assert new_refresh != old_refresh

        # The rotated-out token must be dead.
        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 401


async def test_permission_guard_blocks_unauthorized():
    async with client() as c:
        r = await c.get("/api/v1/auth/me")            # no token at all
        assert r.status_code == 401
        r = await c.post("/api/v1/auth/invitations",  # no token -> guard fires first
                         json={"email": "x@example.com", "role_key": "viewer"})
        assert r.status_code == 401
