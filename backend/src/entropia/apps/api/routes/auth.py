"""Local-auth endpoints (M1 §4): sign up, login, logout.

Sign up and login are anonymous entry flows — they use the DB session directly
instead of the actor-resolving request context. Logout revokes the session
named by the presented Bearer token; it never touches Agent runtimes, queued
jobs, or other users' sessions (M1 §4.3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import auth as auth_commands
from entropia.apps.api.deps import bearer_token, db_session
from entropia.config import get_settings
from entropia.shared.errors import SessionInvalidError

router = APIRouter(prefix="/auth", tags=["auth"])


class SignUpRequest(BaseModel):
    # No role field by design (M1 §4.1): Sign Up can never escalate. Extra
    # client fields (e.g. a smuggled "role") are dropped by pydantic.
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=256)


class SignUpResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    token: str
    session_id: str
    expires_at: str
    user: SignUpResponse


class LogoutResponse(BaseModel):
    session_id: str
    revoked: bool


class BootstrapStatusResponse(BaseModel):
    # Booleans only — no email echo, no PII (see auth_commands.bootstrap_status).
    bootstrap_configured: bool
    active_admin_exists: bool


@router.post("/signup", response_model=SignUpResponse, status_code=201)
async def sign_up(
    body: SignUpRequest,
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> SignUpResponse:
    settings = get_settings()
    result = await auth_commands.sign_up(
        session,
        username=body.username,
        password=body.password,
        email=body.email,
        display_name=body.display_name,
        correlation_id=getattr(request.state, "correlation_id", ""),
        # First-Admin bootstrap opt-in — server-side only, never a client field.
        bootstrap_admin_email=settings.bootstrap_admin_email or None,
    )
    return SignUpResponse(**result)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> LoginResponse:
    settings = get_settings()
    result = await auth_commands.login(
        session,
        username=body.username,
        password=body.password,
        ttl_minutes=settings.auth_session_ttl_minutes,
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return LoginResponse(**result)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> LogoutResponse:
    token = bearer_token(request)
    if token is None:
        raise SessionInvalidError("Logout requires a Bearer session token.")
    result = await auth_commands.logout(
        session,
        token=token,
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return LogoutResponse(session_id=result["session_id"], revoked=result["revoked"])


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
async def bootstrap_status(
    session: AsyncSession = Depends(db_session),
) -> BootstrapStatusResponse:
    """Anonymous, read-only first-Admin onboarding signal (booleans only). Like
    sign up / login it is an unauthenticated entry surface — the first Admin is
    not yet authenticated — and returns no PII, so exposing it carries no more
    than the deployment fact "does an Admin exist yet"."""
    settings = get_settings()
    result = await auth_commands.bootstrap_status(
        session,
        bootstrap_admin_email=settings.bootstrap_admin_email or None,
    )
    return BootstrapStatusResponse(**result)
