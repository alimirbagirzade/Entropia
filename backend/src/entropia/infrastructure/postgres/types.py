"""Helpers for mapping StrEnum domain values to portable VARCHAR+CHECK columns."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=StrEnum)


def enum_column(enum_cls: type[E], name: str) -> SAEnum:
    """A non-native enum column storing the StrEnum's lowercase snake_case values
    with a CHECK constraint (portable, migration-friendly)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )
