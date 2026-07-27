"""Canonical response envelopes shared by every endpoint (Module 19).

- Success collections:  { "data": [...], "meta": { pagination } }
- Success single:        the resource object directly (with ETag header)
- Errors:                { "error": { code, message, details, ids, recovery } }
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from entropia.shared.errors import ErrorCategory

T = TypeVar("T")


class ErrorBody(BaseModel):
    """The one error shape every endpoint emits (doc 01 §11.2, doc 04 §11.1).

    The first five fields are the original Module 19 contract and keep their exact
    names. The recovery block below was added by O-02 so UI and Agent recovery
    consume the same information instead of re-deriving it from ``code`` alone.

    Absent optional values are emitted as explicit ``null`` (never a missing key),
    so a client can read every field unconditionally.
    """

    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str | None = None
    correlation_id: str | None = None
    # Recovery contract. ``details`` is doc 01 §11.2's ``field_issues`` under its
    # shipped name; ``suggested_action`` is the machine token and ``remediation``
    # the human prose (see the adjudication note in ``shared/errors.py``).
    category: ErrorCategory = ErrorCategory.INTERNAL
    retryable: bool = False
    suggested_action: str | None = None
    remediation: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    field_path: str | None = None


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
