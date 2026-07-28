"""Readiness value objects: the immutable finding + the pure-validator inputs
(Stage 4b, doc 14 §9.1-§9.2).

Nothing here touches the DB. The command (orchestrator) resolves the composition
snapshot, each pinned work-object revision payload, the external import batch
state and the allocation config, then hands these plain value objects to the pure
validators (mirrors 4a: ``validate_allocation`` receives resolved ``item_refs``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import (
    ReadinessIssueCode,
    ReadinessScope,
    ReadinessSeverity,
)


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    """A single immutable readiness finding (doc 14 §9.1, §3.2).

    Every issue carries a stable ``code``, ``severity``, ``scope``, an optional
    ``field_path``/``scope_id`` (the composition item it concerns) and a
    human-readable ``message`` + ``remediation`` — the canonical detail the modal
    renders (never DOM-derived, doc 14 §3.2).
    """

    code: ReadinessIssueCode
    severity: ReadinessSeverity
    scope: ReadinessScope
    message: str
    remediation: str | None = None
    field_path: str | None = None
    scope_id: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": str(self.code),
            "severity": str(self.severity),
            "scope": str(self.scope),
            "message": self.message,
            "remediation": self.remediation,
            "field_path": self.field_path,
            "scope_id": self.scope_id,
        }


@dataclass(frozen=True, slots=True)
class ExternalImportState:
    """Resolved canonical import-batch evidence for an external work object
    (doc 14 §5.1 Trading Signal / Trade Log; §9.2 External working objects).

    Resolved by the command from ``canonical_trade_record_batch`` /
    ``normalized_signal_event_revision`` via the pinned ``work_object_revision_id``.
    ``found=False`` means no normalized import revision backs the pinned config —
    a browser file selection alone is never proof: a normalized, accepted import
    revision is required (doc 14 §5.1, Implementation Rules).
    """

    found: bool
    succeeded: bool
    accepted_count: int
    instrument_id: str | None = None
    skipped_reason_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ResearchSourceState:
    """Resolved evidence for ONE Research Data revision a strategy pins (O-01).

    Doc 12 §9.2: "Ready Check and Backtest worker must validate the bundle again
    server-side." Until O-01 the Research layer existed ONLY in the worker
    (``queries/funding.py`` -> ``FundingSourceInvalid``), so a composition pinning
    an ineligible research revision passed Ready Check as READY and then died mid-run.
    The command resolves each pinned revision into this plain value object and the
    pure ``validate_research_sources`` turns it into findings — the same shape as
    ``ExternalImportState`` (no DB access inside the validators).

    ``found`` is False when the pinned revision id resolves to no row at all.
    ``strategy_market_dataset_revision_id`` is the STRATEGY's pinned market revision,
    carried here so the pure validator can compare it against this revision's declared
    link without a second dereference (doc 14 §9.2 "exact Market Data compatibility").
    Every enum-ish field carries the RAW persisted value (never a parsed object), so
    a row written under an older enum member still reaches the validator and is judged
    rather than silently exploding during resolution.
    """

    item_id: str
    revision_id: str
    field_path: str
    found: bool
    root_active: bool = False
    revision_state: str | None = None
    usage_scope: str | None = None
    available_time_policy: str | None = None
    available_delay_seconds: int | None = None
    linked_market_dataset_revision_id: str | None = None
    instrument_mapping_ref: str | None = None
    validation_status: str | None = None
    strategy_market_dataset_revision_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessItemInput:
    """One enabled composition member resolved for validation (doc 14 §9.2).

    ``payload`` is the pinned ``work_object_revision.payload`` (the native config,
    doc 05/04 — a Trade Log/Trading Signal IS a work object). ``available`` is
    False when the pinned root is soft-deleted/inaccessible (RC-16). ``external``
    is the resolved import batch state for the two external kinds, else None.
    """

    item_id: str
    kind: MainboardItemKind
    root_id: str
    revision_id: str
    available: bool
    payload: dict[str, Any]
    external: ExternalImportState | None = None


__all__ = [
    "ExternalImportState",
    "ReadinessIssue",
    "ReadinessItemInput",
    "ResearchSourceState",
]
