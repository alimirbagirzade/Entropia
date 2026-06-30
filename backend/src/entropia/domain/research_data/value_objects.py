"""Immutable research-data value objects (doc 12 §5, §8.3).

Frozen dataclasses with no I/O. Timezone identifiers are validated against the
IANA database via ``zoneinfo``. Category resolution enforces the Other/Custom
requiredness rule (doc 12 §5.1). Field definitions carry the field-level semantic
metadata required by doc 12 §8.3 (FIELD_MEANING_INSUFFICIENT otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchCategory,
    ResearchTimezoneMode,
)
from entropia.shared.errors import (
    CustomCategoryRequired,
    FieldMeaningInsufficient,
    TimePolicyInvalid,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class CategorySpec:
    """A resolved data category. Other/Custom requires a non-empty custom value;
    every other category must not carry one (doc 12 §5.1)."""

    category: ResearchCategory
    custom_category: str | None = None

    def __post_init__(self) -> None:
        if self.category == ResearchCategory.OTHER_CUSTOM:
            if not self.custom_category or not self.custom_category.strip():
                raise CustomCategoryRequired()
        elif self.custom_category is not None:
            raise ValidationError(
                "Only the Other / Custom category may declare a custom category value."
            )

    @property
    def category_key(self) -> str:
        """The persisted, extensible key. For Other/Custom this is the normalized
        custom value; otherwise the built-in enum value."""
        if self.category == ResearchCategory.OTHER_CUSTOM:
            assert self.custom_category is not None  # narrowed by __post_init__
            return self.custom_category.strip()
        return self.category.value


@dataclass(frozen=True, slots=True)
class ResearchTimezoneSpec:
    """Declared source timezone. ``custom`` requires a valid IANA identifier;
    ``utc``/``exchange`` must not carry one (doc 12 §5.2)."""

    mode: ResearchTimezoneMode
    iana: str | None = None

    def __post_init__(self) -> None:
        if self.mode == ResearchTimezoneMode.CUSTOM:
            if not self.iana:
                raise TimePolicyInvalid("A custom timezone requires an IANA identifier.")
            try:
                ZoneInfo(self.iana)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise TimePolicyInvalid(f"'{self.iana}' is not a valid IANA timezone.") from exc
        elif self.iana is not None:
            raise ValidationError("Only the custom timezone mode may declare an IANA identifier.")

    @property
    def zone(self) -> ZoneInfo:
        """Resolve to a concrete ``ZoneInfo`` for deterministic UTC conversion."""
        if self.mode == ResearchTimezoneMode.UTC:
            return ZoneInfo("UTC")
        if self.iana is None:
            raise TimePolicyInvalid("Exchange timezone has no resolvable IANA identifier.")
        return ZoneInfo(self.iana)


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    """Field-level semantic metadata for one native field (doc 12 §8.3).

    All eight attributes are required; an empty ``field_name``/``semantic_type``/
    ``measurement_method``/``null_semantics`` raises ``FieldMeaningInsufficient``
    so a single prose paragraph can never be the sole canonical structure.
    """

    field_name: str
    semantic_type: str
    measurement_method: str
    null_semantics: str
    event_time_source: str
    availability_rule: str
    allowed_usage: str
    unit_or_scale: str | None = None

    def __post_init__(self) -> None:
        required = {
            "field_name": self.field_name,
            "semantic_type": self.semantic_type,
            "measurement_method": self.measurement_method,
            "null_semantics": self.null_semantics,
            "event_time_source": self.event_time_source,
            "availability_rule": self.availability_rule,
            "allowed_usage": self.allowed_usage,
        }
        missing = [name for name, value in required.items() if not value or not value.strip()]
        if missing:
            raise FieldMeaningInsufficient(
                f"Field definition is missing required metadata: {', '.join(sorted(missing))}."
            )


@dataclass(frozen=True, slots=True)
class AvailableTimeSpec:
    """A declared available-time rule. Fixed-delay requires positive seconds;
    every other rule must carry ``delay_seconds = None`` (doc 12 §5.2)."""

    policy: AvailableTimePolicy
    delay_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.policy == AvailableTimePolicy.FIXED_DELAY:
            if self.delay_seconds is None or self.delay_seconds <= 0:
                raise TimePolicyInvalid("Fixed delay must be a positive number of seconds.")
        elif self.delay_seconds is not None:
            raise TimePolicyInvalid("Only the fixed-delay rule may declare a delay.")
