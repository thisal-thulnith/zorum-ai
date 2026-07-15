from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import invitations, service
from app.core.auth.deps import CurrentUser, get_current_user, require_permission, tenant_db
from app.core.auth.models import User
from app.core.auth.schemas import (
    AcceptInviteRequest,
    InviteRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    TokenPair,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/signup", response_model=TokenPair, status_code=201)
async def signup(req: SignupRequest):
    access, refresh = await service.signup(req)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair)
async def login(req: LoginRequest):
    access, refresh = await service.login(req)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(req: RefreshRequest):
    access, new_refresh = await service.refresh(req.refresh_token)
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
async def logout(req: RefreshRequest):
    await service.logout(req.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(tenant_db),
):
    user = (await session.execute(
        select(User).where(User.id == current.user_id)
    )).scalar_one()
    return MeResponse(
        user_id=user.id, tenant_id=user.tenant_id, email=user.email,
        full_name=user.full_name, permissions=current.permissions,
    )


@router.post("/invitations", status_code=201)
async def invite(
    req: InviteRequest,
    current: CurrentUser = Depends(require_permission("users.manage")),
    session: AsyncSession = Depends(tenant_db),
):
    await invitations.create_invitation(
        session, tenant_id=current.tenant_id, actor_id=current.user_id,
        email=req.email, role_key=req.role_key,
    )
    return {"status": "invited"}


@router.post("/invitations/accept", response_model=TokenPair)
async def accept_invite(req: AcceptInviteRequest):
    email = await invitations.accept_invitation(req)
    # Log the new user straight in with the password they just chose.
    access, refresh_token = await service.login(LoginRequest(email=email, password=req.password))
    return TokenPair(access_token=access, refresh_token=refresh_token)
