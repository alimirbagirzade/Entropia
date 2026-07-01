"""Result View Metric Profile pure logic (Stage 5c, doc 17 §5, §7, §11, §14).

No DB, no clock. Validates an Apply selection against a registry snapshot,
normalizes the display order to the registry order (V1 has no drag-reorder — doc
17 §13 Implementation Decision), computes a deterministic ``config_hash`` and
classifies the Apply/Lock/Unlock transition. The minimum-one-selectable rule is
an explicit Implementation Decision (doc 17 §5) so a Result Summary never becomes
an empty container.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from entropia.shared.errors import (
    MetricCodeUnknownError,
    MetricNotSelectableError,
    MetricSelectionEmptyError,
)


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    """The selectable subset of the registry at Apply time (order-preserving).

    ``selectable_order`` maps a selectable code to its registry display order;
    ``known`` is every registry code (selectable or future) for unknown-vs-not-
    selectable discrimination (doc 17 §11 METRIC_CODE_UNKNOWN vs METRIC_NOT_SELECTABLE).
    """

    selectable_order: dict[str, int]
    known: frozenset[str]


def normalize_selection(codes: list[str], registry: RegistrySnapshot) -> list[str]:
    """Validate + normalize an Apply selection to canonical registry order.

    * empty (after de-dup) -> ``MetricSelectionEmptyError`` (doc 17 §5, AT-05)
    * a code absent from the registry -> ``MetricCodeUnknownError`` (§11)
    * a known but non-selectable (future/experimental) code -> ``MetricNotSelectableError``
      (§11, AT-04)
    * duplicates collapse to first occurrence; the result is re-sorted by the
      registry ``display_order`` (V1 has no custom reorder, §13, §14).
    """
    seen: set[str] = set()
    deduped: list[str] = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        if code not in registry.known:
            raise MetricCodeUnknownError()
        if code not in registry.selectable_order:
            raise MetricNotSelectableError(
                f"{code} is not selectable in the current metric registry and cannot be applied."
            )
        deduped.append(code)
    if not deduped:
        raise MetricSelectionEmptyError()
    return sorted(deduped, key=lambda c: registry.selectable_order[c])


def compute_config_hash(
    *, selected_metric_codes: list[str], is_locked: bool, registry_version: str
) -> str:
    """Deterministic hash of a profile revision's presentation config (doc 17 §5.1)."""
    payload = {
        "selected_metric_codes": selected_metric_codes,
        "is_locked": is_locked,
        "registry_version": registry_version,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def transition_reason(*, current_is_locked: bool | None, next_is_locked: bool) -> str:
    """Classify a revision as apply / lock / unlock for the audit reason (doc 17 §7).

    ``current_is_locked`` is ``None`` for the first revision (no prior head). A
    lock-state check (a locked profile refuses an Apply) is enforced by the command
    BEFORE this is called; here we only name the transition.
    """
    if current_is_locked is None:
        return "apply"
    if not current_is_locked and next_is_locked:
        return "lock"
    if current_is_locked and not next_is_locked:
        return "unlock"
    return "apply"


__all__ = [
    "RegistrySnapshot",
    "compute_config_hash",
    "normalize_selection",
    "transition_reason",
]
