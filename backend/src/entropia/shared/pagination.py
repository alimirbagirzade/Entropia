"""Cursor-pagination query parameters shared across list endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class PageParams(BaseModel):
    cursor: str | None = Field(default=None, description="Opaque forward cursor.")
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
