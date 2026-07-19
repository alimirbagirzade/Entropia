"""Portfolio / Equity Allocation typed config (doc 13 §5, §8.2).

Money and percent are ``Decimal`` (NUMERIC-backed), never binary float (doc 13
§13) — the API accepts them as strings and this layer parses them (locale comma
tolerated). Currency / compounding tokens are canonicalized to their uppercase
wire form. ``item_type`` on an entry is advisory only: the command layer derives
the canonical type from the composition item (§8.2), so parsing stays lenient
enough to hold a partial draft — the heavy semantic rules live in ``rules.py``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from entropia.domain.allocation.enums import (
    AllocationCurrency,
    CompoundingMode,
    CrossItemConflictPolicy,
)
from entropia.domain.mainboard.enums import MainboardItemKind


def _to_decimal(value: Any) -> Decimal:
    """Parse a money/percent value to a finite ``Decimal`` (no binary float)."""
    if isinstance(value, bool):
        raise ValueError("A numeric value is required, not a boolean.")
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, float):
        # Money/percent must not travel as binary float (doc 13 §13); the API
        # types these fields as strings so a float here means a non-conforming client.
        raise ValueError("Money and percent must be sent as decimal strings, not floats.")
    elif isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            raise ValueError("A numeric value is required.")
        try:
            parsed = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"'{value}' is not a valid decimal.") from exc
    else:
        raise ValueError("Unsupported numeric type for a money/percent field.")
    if not parsed.is_finite():
        raise ValueError("A finite numeric value is required.")
    return parsed


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MoneyV1(_Strict):
    """A decimal amount with a canonical currency (doc 13 §8.2)."""

    amount: Decimal
    currency: AllocationCurrency

    @field_validator("amount", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> Decimal:
        return _to_decimal(value)

    @field_validator("currency", mode="before")
    @classmethod
    def _norm_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class AllocationEntryV1(_Strict):
    """One allocation row bound to a composition item (doc 13 §5.2, §8.2)."""

    composition_item_id: str
    item_type: MainboardItemKind | None = None
    active: bool = True
    equity_share_percent: Decimal | None = None

    @field_validator("composition_item_id", mode="before")
    @classmethod
    def _strip_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("composition_item_id is required.")
            return stripped
        return value

    @field_validator("item_type", mode="before")
    @classmethod
    def _norm_item_type(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("equity_share_percent", mode="before")
    @classmethod
    def _parse_share(cls, value: Any) -> Any:
        return None if _blank(value) else _to_decimal(value)


class PortfolioAllocationConfigV1(_Strict):
    """The full allocation config; ``enabled=false`` is a valid independent draft."""

    enabled: bool = False
    initial_capital: MoneyV1 | None = None
    compounding_mode: CompoundingMode | None = None
    reserve_cash_percent: Decimal | None = None
    # Portfolio-level rules connecting the item configs (cross-item, doc 13 §8.4):
    # a composition-wide exposure ceiling as a percent of the shared pool P0
    # (``None`` = no cap), and the opposing same-instrument signal policy
    # (``None`` = KEEP_SEPARATE, the pre-rules behaviour).
    max_total_exposure_percent: Decimal | None = None
    conflict_policy: CrossItemConflictPolicy | None = None
    entries: list[AllocationEntryV1] = []

    @field_validator("compounding_mode", mode="before")
    @classmethod
    def _norm_mode(cls, value: Any) -> Any:
        if _blank(value):
            return None
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("reserve_cash_percent", "max_total_exposure_percent", mode="before")
    @classmethod
    def _parse_reserve(cls, value: Any) -> Any:
        return None if _blank(value) else _to_decimal(value)

    @field_validator("conflict_policy", mode="before")
    @classmethod
    def _norm_conflict(cls, value: Any) -> Any:
        if _blank(value):
            return None
        return value.strip().upper() if isinstance(value, str) else value


__all__ = [
    "AllocationEntryV1",
    "MoneyV1",
    "PortfolioAllocationConfigV1",
]
