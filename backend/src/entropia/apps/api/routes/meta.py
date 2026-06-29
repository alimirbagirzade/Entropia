"""Build/runtime metadata for the frontend shell and operators."""

from __future__ import annotations

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


@router.get("", response_model=MetaResponse)
async def meta() -> MetaResponse:
    settings = get_settings()
    return MetaResponse(
        version=__version__,
        environment=settings.environment,
        api_base_path=settings.api_base_path,
    )
