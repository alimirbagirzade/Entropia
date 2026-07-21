"""Local-auth endpoints (M1 §4): sign up, login, logout.

Sign up and login are anonymous entry flows — they use the DB session directly
instead of the actor-resolving request context. Logout revokes the session
named by the presented Bearer token; it never touches Agent runtimes, queued
jobs, or other users' sessions (M1 §4.3).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import auth as auth_commands
from entropia.apps.api.deps import RequestContext, bearer_token, db_session, request_context
from entropia.config import get_settings
from entropia.domain.identity.policy import require_authenticated
from entropia.shared.errors import AuthModeMismatchError, SessionInvalidError

router = APIRouter(prefix="/auth", tags=["auth"])

# F-21 purposes a re-authentication proof may be minted for — a closed set so
# a client can never scope a proof to an action it wasn't actually issued for.
ReauthPurpose = Literal["trash_purge"]


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


class ReauthRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)
    purpose: ReauthPurpose


class ReauthResponse(BaseModel):
    reauth_proof: str
    expires_at: str


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
    # BACK-01: issuance and acceptance are ONE decision. Under AUTH_MODE=dev the
    # request pipeline ignores Bearer sessions entirely (deps.py resolves only
    # X-Actor-Id), so minting a session here would hand the caller a token that
    # is dead on arrival — the "login 200 -> protected 401" mismatch. Fail before
    # touching credentials: no hash is verified, no session row is written, and
    # no login audit event is emitted for a mode that cannot honour the result.
    if settings.auth_mode != "session":
        raise AuthModeMismatchError
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


@router.post("/reauth", response_model=ReauthResponse)
async def reauth(
    body: ReauthRequest,
    request: Request,
    ctx: RequestContext = Depends(request_context),
) -> ReauthResponse:
    """F-21: re-verify the ALREADY-authenticated actor's password and mint a
    short-lived, single-use, purpose-scoped proof (doc 20 §8.3). Requires the
    same session the client is already using — this is a re-auth STEP, not a
    second login. A non-human actor (Agent/service line) or an unknown
    password both fall through to the same 401 INVALID_CREDENTIALS as login
    (:func:`auth_commands.reauthenticate` resolves no ``HumanUser`` row for a
    non-human principal id and rejects uniformly)."""
    require_authenticated(ctx.actor)
    settings = get_settings()
    result = await auth_commands.reauthenticate(
        ctx.session,
        user_id=ctx.actor.principal_id or "",
        password=body.password,
        purpose=body.purpose,
        ttl_minutes=settings.reauth_proof_ttl_minutes,
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return ReauthResponse(**result)
