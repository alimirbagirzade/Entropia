"""Build/runtime metadata for the frontend shell and operators."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from entropia import __version__
from entropia.config import get_settings

router = APIRouter(prefix="/meta", tags=["meta"])


class MetaResponse(BaseModel):
    name: str = "Entropia V18"
    version: str
    environment: str
    api_base_path: str
    # The trust model the API actually enforces (deps.py). The shell MUST pick its
    # auth UI and its request credential from this value rather than from "a token
    # exists in localStorage": under AUTH_MODE=dev a stored Bearer token is ignored
    # by the server, so a token-driven UI hides DevActorControl and leaves every
    # protected request anonymous (the login 200 -> protected 401 mismatch).
    # Non-secret by construction: a closed enum naming the mechanism — never a
    # token, a bootstrap email, or service-token state.
    auth_mode: Literal["dev", "session"]


@router.get("", response_model=MetaResponse)
async def meta() -> MetaResponse:
    settings = get_settings()
    return MetaResponse(
        version=__version__,
        environment=settings.environment,
        api_base_path=settings.api_base_path,
        auth_mode=settings.auth_mode,
    )
