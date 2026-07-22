"""Identity endpoints (M1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from entropia.application.commands.roles import change_user_role
from entropia.apps.api.deps import RequestContext, request_context
from entropia.config import get_settings
from entropia.domain.identity.policy import require_admin
from entropia.domain.lifecycle.enums import Role

router = APIRouter(tags=["identity"])


class MeResponse(BaseModel):
    principal_id: str | None
    principal_type: str
    role: str | None
    is_admin: bool
    is_authenticated: bool


class ChangeRoleRequest(BaseModel):
    role: Role


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: str
    version: int


@router.get("/me", response_model=MeResponse)
async def me(ctx: RequestContext = Depends(request_context)) -> MeResponse:
    a = ctx.actor
    return MeResponse(
        principal_id=a.principal_id,
        principal_type=str(a.principal_type),
        role=str(a.role) if a.role else None,
        is_admin=a.is_admin,
        is_authenticated=a.is_authenticated,
    )


@router.post("/users/{user_id}/role", response_model=UserResponse)
async def set_user_role(
    user_id: str,
    body: ChangeRoleRequest,
    ctx: RequestContext = Depends(request_context),
) -> UserResponse:
    require_admin(ctx.actor)  # fast 403 before touching domain
    user = await change_user_role(
        ctx.session,
        ctx.actor,
        target_user_id=user_id,
        new_role=body.role,
        # Mode-aware last-Admin protection (PROV-03) on the legacy role path too.
        auth_mode=get_settings().auth_mode,
    )
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        role=str(user.current_role),
        version=user.version,
    )
