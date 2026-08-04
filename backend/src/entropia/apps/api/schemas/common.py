"""Envelope pieces shared by more than one paginated read model."""

from __future__ import annotations

from pydantic import BaseModel


class CursorPageMeta(BaseModel):
    """The cursor-pagination envelope: ``{"cursor": <next|null>, "has_more": bool}``.

    ``cursor`` is REQUIRED-and-nullable, not optional: the key is always present and carries
    ``null`` on the last page. Callers page by testing ``has_more``, never by testing key
    presence."""

    cursor: str | None
    has_more: bool


__all__ = ["CursorPageMeta"]
