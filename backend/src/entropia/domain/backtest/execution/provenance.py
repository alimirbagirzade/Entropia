"""Unified-clock portfolio provenance: the run manifest section + ledger artifact ref.

ADIM 19. CONTAINED — nothing in production imports this module, exactly like
``clock``/``intents``/``portfolio_ledger``/``arbitration``. It is the record a unified
co-simulation must pin so a Result can be re-derived and audited without ever joining a
live composition (doc 13 §13, Modül 11 §10, ADR 0002 §10).

Three rules shape the design.

**1. Canon owns the field names.** Modül 11 §10 (`:8313-8333`) writes the shape literally:
``plan_revision_id``, ``enabled``, ``initial_capital``, ``reserve_amount``,
``compounding_mode``, ``entries[].{composition_item_snapshot_id, item_revision_id,
share_percent, initial_sleeve_capital}`` and ``engine_allocation_policy_version``. Those
names are reproduced verbatim; nothing here renames them.

**2. Display labels never touch the hash.** ``identity`` is a sha256 over
:meth:`PortfolioManifest.execution_content` only. Item labels ride in ``presentation``,
outside that content — the same split ``manifest.pinned_item_labels`` already makes for the
sequential manifest (``manifest.py:160-185``): renaming a composition item must never fork a
run's reproducibility identity.

**3. A decided-but-unbuilt policy is disclosed, never assumed.** ADR 0002 §13 OD-2 (how an
open position is marked at a tick with no fresh bar of its own) was RESOLVED on 2026-08-05 to
option (a) — carry the last closed bar's close forward under a declared ``stale_after`` bound
with a diagnostic counter (§13.1). §13.1 assigned both the mark policy and this label's flip
to ADIM 20, and ADIM 20 landed them TOGETHER: ``MARK_STALENESS_POLICY`` now reads
``"carry_forward_bounded_v1"`` and the behaviour behind it is
``portfolio_ledger.MarkPrice.is_usable`` bounded by ``MARK_STALE_AFTER_MS``. The pairing was
the point — flipping the label before the bound existed would have advertised a behaviour no
artifact could show. ``arbitration.CONTENTION_SELECTION_STATUS`` was the same shape for OD-3
and flipped in the same slice, though for the opposite reason: there the behaviour had shipped
long before and only the label was waiting.

The allocation amounts are NOT recomputed here. They are the numbers the server already
derived and froze onto ``PortfolioAllocationPlanRevision.derived_amounts``
(``allocation_plan.py:380``) — the same figures the user previewed. ``SleevePlan`` computes
its own unquantized sleeves for execution; :func:`sleeve_amount_divergences` proves the two
agree and REPORTS where they do not, instead of silently preferring one (doc 13 §13:
*"float rounding ile manifest/preview mismatch üretme"*).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from entropia.domain.backtest.artifacts import (
    ARTIFACT_CHECKSUM_SCHEMA_VERSION,
    ArtifactType,
    compute_artifact_checksum,
)
from entropia.domain.backtest.execution.arbitration import (
    ARBITRATION_POLICY_VERSION,
    CONTENTION_SELECTION_POLICY,
    CONTENTION_SELECTION_STATUS,
    ConflictPolicyRule,
    resolve_policy,
)
from entropia.domain.backtest.execution.attribution import (
    ATTRIBUTION_POLICY_VERSION,
    CONTRIBUTION_METHOD,
)
from entropia.domain.backtest.execution.clock import CLOCK_POLICY_VERSION, timeline_identity
from entropia.domain.backtest.execution.constants import _MONEY
from entropia.domain.backtest.execution.intents import INTENT_CONTRACT_VERSION, ItemIdentity
from entropia.domain.backtest.execution.portfolio_ledger import (
    LEDGER_POLICY_VERSION,
    MONEY_QUANTUM,
    MONEY_ROUNDING,
    QTY_QUANTUM,
    PortfolioEquityPoint,
    SleevePlan,
)
from entropia.shared.manifest import manifest_hash

#: This module's own contract version. Bump when the emitted SHAPE changes.
PORTFOLIO_MANIFEST_VERSION = "portfolio-manifest-v1"

#: Modül 11 §10 fixes this literal; it is canon, not a local choice.
ENGINE_ALLOCATION_POLICY_VERSION = "portfolio-allocation-v1"

#: ADR 0002 §13 OD-2 is DECIDED — (a), carry forward under a declared ``stale_after`` bound
#: with a diagnostic counter (§13.1, 2026-08-05) — and as of ADIM 20 it is also BUILT
#: (containment-lift precondition 17). §13.1 gave ADIM 20 both the mark policy and this
#: label's flip, and they land together on purpose: the previous values advertised the
#: ABSENCE rather than a default, so flipping the label before the bound existed would have
#: hidden the gap inside an artifact just as surely as guessing a bound would have.
#:
#: The bound itself is ``portfolio_ledger.MARK_STALE_AFTER_MS`` and is part of THIS version —
#: changing the number requires a new ``carry_forward_bounded_vN`` and an ``ENGINE_VERSION``
#: bump, or two Results marked under different bounds would share one namespace (R-5).
MARK_STALENESS_POLICY = "carry_forward_bounded_v1"
MARK_STALENESS_STATUS = "built"
MARK_STALENESS_TRACKING = "ADR 0002 §13 OD-2"

#: Emitted when the frozen preview amount and the executed sleeve disagree at a
#: quantization tie. ``allocation.rules._money`` rounds HALF_UP while the ledger's money
#: step is HALF_EVEN, so ``1000.10`` at 25 % previews ``250.03`` and executes ``250.025``.
SLEEVE_AMOUNT_DIVERGENCE = "sleeve_amount_preview_execution_divergence"


class ProvenanceError(ValueError):
    """Base for every refusal in this module."""


class MissingAllocationProvenanceError(ProvenanceError):
    """A shared-mode manifest was requested without the frozen allocation record."""


class UnknownProvenanceItemError(ProvenanceError):
    """An item appears in one pinned projection but not another."""


class DuplicatePinOrdinalError(ProvenanceError):
    """Two items claim the same pin ordinal — the merge order would be ambiguous."""


def money_str(value: Decimal) -> str:
    """The canonical MANIFEST spelling of a money amount.

    Public because the provenance section is now assembled by a sibling module
    (``portfolio_projection.build_portfolio_provenance``) that must spell an executed
    sleeve exactly as :func:`sleeve_amount_divergences` spells it when it compares one — a
    second local formatter there could drift by a rounding mode and turn an agreement into
    a reported divergence, or hide a real one."""
    return str(value.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING))


@dataclass(frozen=True, slots=True)
class SleeveProvenance:
    """One frozen allocation entry, in Modül 11 §10's own field names."""

    composition_item_snapshot_id: str
    item_revision_id: str | None
    share_percent: str
    initial_sleeve_capital: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "composition_item_snapshot_id": self.composition_item_snapshot_id,
            "item_revision_id": self.item_revision_id,
            "share_percent": self.share_percent,
            "initial_sleeve_capital": self.initial_sleeve_capital,
        }


@dataclass(frozen=True, slots=True)
class AllocationProvenance:
    """``backtest_run_manifest.portfolio_allocation`` (Modül 11 §10, doc 13 §13).

    Every amount is a decimal STRING copied from the frozen revision's
    ``derived_amounts`` — never re-derived here, so the manifest cannot drift from what the
    user was shown and what the revision persisted (doc 13 §5.3, §8.5)."""

    enabled: bool
    plan_id: str | None
    plan_revision_id: str | None
    config_hash: str | None
    base_currency: str | None
    compounding_mode: str | None
    initial_capital: str | None
    reserve_amount: str | None
    capital_available: str | None
    total_allocated: str | None
    unallocated: str | None
    active_share_total: str | None
    entries: tuple[SleeveProvenance, ...] = ()
    fx_refs: tuple[str, ...] = ()
    engine_allocation_policy_version: str = ENGINE_ALLOCATION_POLICY_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "plan_id": self.plan_id,
            "plan_revision_id": self.plan_revision_id,
            "config_hash": self.config_hash,
            "base_currency": self.base_currency,
            "compounding_mode": self.compounding_mode,
            "initial_capital": self.initial_capital,
            "reserve_amount": self.reserve_amount,
            "capital_available": self.capital_available,
            "total_allocated": self.total_allocated,
            "unallocated": self.unallocated,
            "active_share_total": self.active_share_total,
            "entries": [entry.as_dict() for entry in self.entries],
            "fx_refs": list(self.fx_refs),
            "engine_allocation_policy_version": self.engine_allocation_policy_version,
        }


def independent_allocation_provenance() -> AllocationProvenance:
    """Independent mode. doc 13 §13: the revision id may be null, but ``enabled=false``
    must be EXPLICIT — an absent block would read as "unknown", not as "off"."""
    return AllocationProvenance(
        enabled=False,
        plan_id=None,
        plan_revision_id=None,
        config_hash=None,
        base_currency=None,
        compounding_mode=None,
        initial_capital=None,
        reserve_amount=None,
        capital_available=None,
        total_allocated=None,
        unallocated=None,
        active_share_total=None,
    )


def allocation_provenance_from_derived(
    derived: Mapping[str, Any],
    *,
    plan_id: str,
    plan_revision_id: str | None,
    config_hash: str | None,
    compounding_mode: str,
    item_revision_ids: Mapping[str, str | None] | None = None,
    fx_refs: Sequence[str] = (),
) -> AllocationProvenance:
    """Project a FROZEN ``derived_amounts`` payload into the canonical manifest block.

    ``derived`` is ``allocation.rules.DerivedAmounts.as_dict()`` as persisted on
    ``PortfolioAllocationPlanRevision.derived_amounts``. Nothing is recomputed: an amount
    that is absent stays ``None`` rather than being invented from the config."""
    raw_sleeves = derived.get("sleeves") or []
    revisions = item_revision_ids or {}
    entries = tuple(
        SleeveProvenance(
            composition_item_snapshot_id=str(sleeve["composition_item_id"]),
            item_revision_id=revisions.get(str(sleeve["composition_item_id"])),
            share_percent=str(sleeve["equity_share_percent"]),
            initial_sleeve_capital=str(sleeve["initial_sleeve_capital"]),
        )
        for sleeve in raw_sleeves
        if isinstance(sleeve, Mapping)
    )
    return AllocationProvenance(
        enabled=True,
        plan_id=plan_id,
        plan_revision_id=plan_revision_id,
        config_hash=config_hash,
        base_currency=_opt_str(derived.get("currency")),
        compounding_mode=compounding_mode,
        initial_capital=_opt_str(derived.get("portfolio_initial_capital")),
        reserve_amount=_opt_str(derived.get("reserved_cash")),
        capital_available=_opt_str(derived.get("capital_available")),
        total_allocated=_opt_str(derived.get("total_allocated")),
        unallocated=_opt_str(derived.get("unallocated")),
        active_share_total=_opt_str(derived.get("active_share_total")),
        entries=entries,
        fx_refs=tuple(str(ref) for ref in fx_refs),
    )


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def sleeve_amount_divergences(
    allocation: AllocationProvenance, plan: SleevePlan
) -> tuple[dict[str, Any], ...]:
    """Report every entry whose frozen preview amount differs from the executed sleeve.

    Returns an empty tuple when they agree. This exists because the two paths quantize
    differently — ``allocation.rules._money`` is ROUND_HALF_UP, ``portfolio_ledger``'s money
    step is ROUND_HALF_EVEN — so a half-cent tie makes the previewed sleeve and the executed
    one disagree by one cent. doc 13 §13 forbids a preview/manifest mismatch, and the
    canonical rounding rule for this tie is not decided anywhere, so the divergence is
    SURFACED rather than resolved."""
    findings: list[dict[str, Any]] = []
    for entry in allocation.entries:
        item_id = entry.composition_item_snapshot_id
        executed = plan.initial_sleeves.get(item_id)
        if executed is None:
            raise UnknownProvenanceItemError(
                f"Allocation entry {item_id!r} has no sleeve in the executed plan."
            )
        if money_str(executed) != entry.initial_sleeve_capital:
            findings.append(
                {
                    "code": SLEEVE_AMOUNT_DIVERGENCE,
                    "composition_item_snapshot_id": item_id,
                    "manifest_initial_sleeve_capital": entry.initial_sleeve_capital,
                    "executed_sleeve_capital": money_str(executed),
                    "executed_sleeve_capital_exact": str(executed),
                }
            )
    return tuple(findings)


@dataclass(frozen=True, slots=True)
class PinnedItem:
    """One executing item's pinned identity + the data revisions it replayed.

    ``item_label`` is DELIBERATELY absent — labels live in ``presentation`` so they cannot
    reach the hash."""

    item_id: str
    pin_ordinal: int
    item_kind: str
    root_id: str | None
    selected_revision_id: str | None
    data_revisions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "data_revisions", MappingProxyType(dict(sorted(self.data_revisions.items())))
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "pin_ordinal": self.pin_ordinal,
            "item_kind": self.item_kind,
            "root_id": self.root_id,
            "selected_revision_id": self.selected_revision_id,
            "data_revisions": dict(self.data_revisions),
        }


def pinned_items_from_identities(
    identities: Sequence[ItemIdentity],
    *,
    data_revisions: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[PinnedItem, ...]:
    """Project the intent layer's ``ItemIdentity`` into pinned manifest rows.

    Ordered by ``(pin_ordinal, item_id)`` — the same total order the clock merges on
    (``clock._ordered_streams``), so the manifest records the order that actually ran."""
    per_item = data_revisions or {}
    seen: dict[int, str] = {}
    for identity in identities:
        clash = seen.get(identity.pin_ordinal)
        if clash is not None:
            raise DuplicatePinOrdinalError(
                f"Items {clash!r} and {identity.item_id!r} share pin ordinal "
                f"{identity.pin_ordinal}."
            )
        seen[identity.pin_ordinal] = identity.item_id
    return tuple(
        PinnedItem(
            item_id=identity.item_id,
            pin_ordinal=identity.pin_ordinal,
            item_kind=identity.item_kind,
            root_id=identity.root_id,
            selected_revision_id=identity.selected_revision_id,
            data_revisions=dict(per_item.get(identity.item_id, {})),
        )
        for identity in sorted(identities, key=lambda i: (i.pin_ordinal, i.item_id))
    )


def item_labels_from_identities(identities: Sequence[ItemIdentity]) -> dict[str, str]:
    """The presentation half — never hashed (mirrors ``manifest.pinned_item_labels``)."""
    return {
        identity.item_id: identity.item_label
        for identity in sorted(identities, key=lambda i: (i.pin_ordinal, i.item_id))
        if identity.item_label
    }


@dataclass(frozen=True, slots=True)
class LedgerArtifactRef:
    """An immutable reference to the shared ledger's published equity series.

    Reuses the shipped artifact checksum (``artifacts.compute_artifact_checksum``) rather
    than inventing a second hashing scheme, so a manifest reference and the persisted
    ``result_artifact_checksum`` row are verifiable against each other."""

    artifact_type: str
    row_count: int
    checksum: str
    schema_version: str = ARTIFACT_CHECKSUM_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "row_count": self.row_count,
            "checksum": self.checksum,
            "schema_version": self.schema_version,
        }


def ledger_equity_rows(points: Sequence[PortfolioEquityPoint]) -> list[dict[str, Any]]:
    """The canonical row projection the checksum is taken over.

    ``t_ms`` is emitted for every point including the seed (whose ``t_ms`` is ``None``), so
    a series that gains a seed point cannot collide with one that never had it."""
    return [
        {
            "seq": point.seq,
            "t_ms": point.t_ms,
            "equity": str(point.equity),
            "drawdown": str(point.drawdown),
            "gross_exposure_percent": str(point.gross_exposure_percent),
        }
        for point in points
    ]


def ledger_artifact_ref(points: Sequence[PortfolioEquityPoint]) -> LedgerArtifactRef:
    rows = ledger_equity_rows(points)
    return LedgerArtifactRef(
        artifact_type=str(ArtifactType.EQUITY_CURVE),
        row_count=len(rows),
        checksum=compute_artifact_checksum(ArtifactType.EQUITY_CURVE, rows),
    )


@dataclass(frozen=True, slots=True)
class PortfolioManifest:
    """The unified-clock manifest section + its content identity."""

    engine_version: str
    allocation: AllocationProvenance
    items: tuple[PinnedItem, ...]
    conflict_policy: ConflictPolicyRule
    ledger_artifact: LedgerArtifactRef | None
    timeline_identity: str
    tick_count: int
    first_t_ms: int | None
    last_t_ms: int | None
    item_labels: Mapping[str, str] = field(default_factory=dict)
    divergences: tuple[dict[str, Any], ...] = ()
    manifest_version: str = PORTFOLIO_MANIFEST_VERSION
    identity: str = field(default="", compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_labels", MappingProxyType(dict(self.item_labels)))
        object.__setattr__(self, "identity", manifest_hash(self.execution_content()))

    def policy_versions(self) -> dict[str, Any]:
        """Every knob whose value changes what a replay produces."""
        return {
            "portfolio_manifest_version": self.manifest_version,
            "engine_version": self.engine_version,
            "clock_policy_version": CLOCK_POLICY_VERSION,
            "intent_contract_version": INTENT_CONTRACT_VERSION,
            "portfolio_ledger_policy_version": LEDGER_POLICY_VERSION,
            "arbitration_policy_version": ARBITRATION_POLICY_VERSION,
            "engine_allocation_policy_version": (self.allocation.engine_allocation_policy_version),
            "attribution_policy_version": ATTRIBUTION_POLICY_VERSION,
            "contribution_method": CONTRIBUTION_METHOD,
            "money_quantum": str(_MONEY),
            "quantity_quantum": str(QTY_QUANTUM),
            "money_rounding": str(MONEY_ROUNDING),
            "mark_staleness_policy": MARK_STALENESS_POLICY,
            "mark_staleness_status": MARK_STALENESS_STATUS,
            "mark_staleness_tracking": MARK_STALENESS_TRACKING,
        }

    def execution_content(self) -> dict[str, Any]:
        """What ``identity`` hashes. Display labels are NOT in here — see the module
        docstring, rule 2."""
        return {
            "policy_versions": self.policy_versions(),
            "portfolio_allocation": self.allocation.as_dict(),
            "items": [item.as_dict() for item in self.items],
            "conflict_policy": {
                "policy": self.conflict_policy.policy,
                "supported": self.conflict_policy.supported,
                "opposite_same_instrument": self.conflict_policy.opposite_same_instrument,
                "same_direction_same_instrument": (
                    self.conflict_policy.same_direction_same_instrument
                ),
                "separate_position_books": self.conflict_policy.separate_position_books,
                "shares_capital": self.conflict_policy.shares_capital,
                "canon": self.conflict_policy.canon,
                "undefined_semantics": list(self.conflict_policy.undefined_semantics),
                "selection_policy": CONTENTION_SELECTION_POLICY,
                "selection_status": CONTENTION_SELECTION_STATUS,
            },
            "time_alignment": {
                "timeline_identity": self.timeline_identity,
                "tick_count": self.tick_count,
                "first_t_ms": self.first_t_ms,
                "last_t_ms": self.last_t_ms,
            },
            "ledger_artifact": (
                None if self.ledger_artifact is None else self.ledger_artifact.as_dict()
            ),
        }

    def as_dict(self) -> dict[str, Any]:
        content = self.execution_content()
        content["identity"] = self.identity
        content["presentation"] = {"item_labels": dict(self.item_labels)}
        content["divergences"] = [dict(row) for row in self.divergences]
        return content


def build_portfolio_manifest(
    *,
    engine_version: str,
    allocation: AllocationProvenance,
    identities: Sequence[ItemIdentity],
    conflict_policy: ConflictPolicyRule | str | None,
    tick_instants: Sequence[int],
    equity_points: Sequence[PortfolioEquityPoint] = (),
    plan: SleevePlan | None = None,
    data_revisions: Mapping[str, Mapping[str, str]] | None = None,
) -> PortfolioManifest:
    """Assemble the manifest section. Pure: no DB, no clock, no randomness.

    ``conflict_policy`` takes either the resolved :class:`ConflictPolicyRule` or the raw
    token the run manifest pinned (``None`` / blank being the absence of a cross-item rule,
    which is KEEP_SEPARATE by definition). Resolving a token is THIS module's job rather
    than its callers': pinning the resolved rule is precisely why provenance is one of the
    three named modules allowed to import the arbitration layer
    (``test_backtest_cross_item_arbitration.py``'s importer allowlist, signed 2026-08-18).
    Having the section's assembler resolve it instead would have made that assembler a
    FOURTH importer of a human-signed list — measured, not hypothetical: it turned that
    guard red.

    ``plan`` is optional and used ONLY to cross-check the frozen sleeve amounts against
    what will actually execute; passing it never changes an amount, it only populates
    ``divergences``."""
    if allocation.enabled and allocation.plan_revision_id is None and not allocation.entries:
        raise MissingAllocationProvenanceError(
            "A shared-mode manifest needs the frozen allocation record (doc 13 §13)."
        )
    rule = (
        conflict_policy
        if isinstance(conflict_policy, ConflictPolicyRule)
        else resolve_policy(conflict_policy)
    )
    instants = sorted(set(tick_instants))
    divergences = (
        sleeve_amount_divergences(allocation, plan)
        if plan is not None and allocation.enabled
        else ()
    )
    return PortfolioManifest(
        engine_version=engine_version,
        allocation=allocation,
        items=pinned_items_from_identities(identities, data_revisions=data_revisions),
        conflict_policy=rule,
        ledger_artifact=ledger_artifact_ref(equity_points) if equity_points else None,
        timeline_identity=timeline_identity(instants),
        tick_count=len(instants),
        first_t_ms=instants[0] if instants else None,
        last_t_ms=instants[-1] if instants else None,
        item_labels=item_labels_from_identities(identities),
        divergences=divergences,
    )


__all__ = [
    "ARBITRATION_POLICY_VERSION",
    "ATTRIBUTION_POLICY_VERSION",
    "CLOCK_POLICY_VERSION",
    "CONTRIBUTION_METHOD",
    "ENGINE_ALLOCATION_POLICY_VERSION",
    "MARK_STALENESS_POLICY",
    "MARK_STALENESS_STATUS",
    "MARK_STALENESS_TRACKING",
    "PORTFOLIO_MANIFEST_VERSION",
    "SLEEVE_AMOUNT_DIVERGENCE",
    "AllocationProvenance",
    "DuplicatePinOrdinalError",
    "LedgerArtifactRef",
    "MissingAllocationProvenanceError",
    "PinnedItem",
    "PortfolioManifest",
    "ProvenanceError",
    "SleeveProvenance",
    "UnknownProvenanceItemError",
    "allocation_provenance_from_derived",
    "build_portfolio_manifest",
    "independent_allocation_provenance",
    "item_labels_from_identities",
    "ledger_artifact_ref",
    "ledger_equity_rows",
    "money_str",
    "pinned_items_from_identities",
    "sleeve_amount_divergences",
]
