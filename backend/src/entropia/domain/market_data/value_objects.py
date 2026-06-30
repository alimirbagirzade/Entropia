"""Immutable market-data value objects (doc 11 §).

Frozen dataclasses with no I/O. Timezone identifiers are validated against the
IANA database via ``zoneinfo``. Numeric coverage values use ``str``/``Decimal``,
never Python ``float`` (project DB rule D6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from entropia.domain.market_data.enums import ResolutionKind, TimezoneMode
from entropia.shared.errors import TimezoneRequired, ValidationError


@dataclass(frozen=True, slots=True)
class Resolution:
    """A dataset cadence. ``value`` is e.g. ``"15m"``/``"1h"``/``"1D"`` for bar
    resolutions, or ``None`` for event-based data."""

    kind: ResolutionKind
    value: str | None = None

    def __post_init__(self) -> None:
        if self.kind == ResolutionKind.BAR and not self.value:
            raise ValidationError("A bar resolution requires an explicit cadence value.")
        if self.kind == ResolutionKind.EVENT_BASED and self.value:
            raise ValidationError("Event-based data must not declare a bar cadence value.")


@dataclass(frozen=True, slots=True)
class TimezoneSpec:
    """Declared source timezone. ``custom`` requires a valid IANA identifier;
    ``exchange``/``utc`` must not carry one."""

    mode: TimezoneMode
    iana: str | None = None

    def __post_init__(self) -> None:
        if self.mode == TimezoneMode.CUSTOM:
            if not self.iana:
                raise TimezoneRequired()
            try:
                ZoneInfo(self.iana)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValidationError(f"'{self.iana}' is not a valid IANA timezone.") from exc
        elif self.iana is not None:
            raise ValidationError("Only the custom timezone mode may declare an IANA identifier.")

    @property
    def zone(self) -> ZoneInfo:
        """Resolve to a concrete ``ZoneInfo`` for deterministic UTC conversion."""
        if self.mode == TimezoneMode.UTC:
            return ZoneInfo("UTC")
        if self.iana is None:
            raise ValidationError("Exchange timezone has no resolvable IANA identifier.")
        return ZoneInfo(self.iana)


@dataclass(frozen=True, slots=True)
class CoverageSlice:
    """A contiguous covered interval for a dataset, with an optional row count."""

    start: datetime
    end: datetime
    row_count: int | None = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError("Coverage slice end must not precede its start.")
        if self.row_count is not None and self.row_count < 0:
            raise ValidationError("Coverage slice row count must be non-negative.")
