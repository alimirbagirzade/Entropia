"""Canonical response envelopes shared by every endpoint (Module 19).

- Success collections:  { "data": [...], "meta": { pagination } }
- Success single:        the resource object directly (with ETag header)
- Errors:                { "error": { code, message, details, ids } }
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str | None = None
    correlation_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class PageMeta(BaseModel):
    """Cursor-based pagination metadata (preferred for large datasets)."""

    cursor: str | None = None
    has_more: bool = False
    total: int | None = None


class Page(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta = Field(default_factory=PageMeta)
