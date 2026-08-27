"""Portfolio / Equity Allocation semantic validation, capital formulas and the
canonical config hash (doc 13 §8.3, §10.1, §13, §14).

Pure and deterministic: the command layer resolves composition-item availability
and passes it in as ``item_refs`` — nothing here touches the DB. Money is
quantized to 2dp (V1 currencies are all 2dp), percents keep their entered scale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256

from entropia.domain.allocation.capability import (
    SHARED_ALLOCATION_FIELD_PATH,
    SHARED_ALLOCATION_MESSAGE,
    shared_allocation_is_executable,
)
from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.enums import AllocationIssueCode as Code
from entropia.domain.allocation.enums import AllocationIssueSeverity as Sev
from entropia.domain.allocation.enums import CrossItemConflictPolicy as ConflictPolicy
from entropia.domain.mainboard.enums import MainboardItemKind

_HUNDRED = Decimal(100)
_ZERO = Decimal(0)
_MONEY_Q = Decimal("0.01")

# The composition-item kinds that may be allocated a capital sleeve (doc 13 §5.2
# "selected item ... must be compatible", §14#8 "compatible Strategy, Trading Signal
# or Trade Log items").
#
# ``MainboardItemKind`` currently holds exactly these three, so the guard used to be
# IMPLICIT: the command layer server-derives ``item_type`` from the composition item
# and an unknown id is already DEPENDENCY_BLOCKED, which made a spoofed kind
# unreachable — but nothing in this validator ever read ``ref.kind``. The set is
# spelled out here so widening the enum with a non-allocatable kind fails CLOSED at
# validation instead of silently earning a sleeve (I-03).
ALLOCATABLE_ITEM_KINDS: frozenset[MainboardItemKind] = frozenset(
    {
        MainboardItemKind.STRATEGY,
        MainboardItemKind.TRADING_SIGNAL,
        MainboardItemKind.TRADE_LOG,
    }
)


# ---- NET cross-item conflict policy: the notice (G14 / GH #544, Decision C) ---- #
#
# Signed 2026-08-26, ``docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md``
# Decision 1 = "C now + B (REMOVE) before C9", Decision 3 = the text below. The value is
# NOT removed by this slice (that is `B`, and it is a migration), so what ships here is
# only the notice — and the notice had been counter-factual since it was written.
#
# WHY THE LEADING CLAUSE IS DERIVED AND NOT SPELLED OUT. Under containment no shared plan
# reaches an engine at all, so "the engine executes NET as BLOCK_OPPOSITE" describes
# something that cannot happen; but hard-coding "nothing runs" would itself become a lie
# the day `C9` lifts the flag. So the first clause is a function of
# ``shared_allocation_is_executable()`` and the message is honest in BOTH worlds — which
# is what ``test_shared_allocation_two_world_gate`` measures.
#
# WHY THE FIVE SEMANTICS ARE NAMED, NOT IMPORTED. They are enumerated in
# ``domain/backtest/execution/arbitration.py`` under ``NET_UNDEFINED_SEMANTICS``, which is
# a phase-loop module: the signed containment allowlist
# (``test_oracle_portfolio_containment_gate::_AUTHORISED_PHASE_LOOP_IMPORTERS``) scans for
# the literal text of such an import, so importing it here would widen a SIGNED list by an
# unsigned module. Naming the symbol costs nothing and keeps the guard meaningful.
_NET_POLICY_BODY = (
    "NET has no canonical definition: neither doc 13 nor Master Ref Modül 11 §6.3 states a "
    "netting price, position custody, fee attribution, realized-PnL attribution or margin "
    "treatment for an offset pair (the five are enumerated in "
    "domain/backtest/execution/arbitration.py under NET_UNDEFINED_SEMANTICS). The two "
    "engines consequently disagree about the value: the V1 sequential engine downgrades NET "
    "to BLOCK_OPPOSITE and discloses the downgrade (a later-pinned item's opposing "
    "same-instrument entry is blocked, never netted-filled), while the unified-clock phase "
    "loop REFUSES a NET run outright rather than label a block as netting. Choose "
    "BLOCK_OPPOSITE or KEEP_SEPARATE to say which of those two you actually want (GH #544)."
)

_NET_POLICY_NOT_EXECUTABLE_PREFIX = (
    "Shared capital allocation does not execute in this build, so no plan carrying this "
    "policy reaches an engine at all and the downgrade described below does not happen. "
)


def _net_policy_warning(*, shared_is_executable: bool) -> str:
    """The CONFLICT_POLICY_NET_V1 message, told against the world that actually applies.

    The body is the part that is true whatever the flag says; the prefix is the part that
    is true only while shared capital is contained. Keeping them separate is the whole
    point — a single frozen string cannot be right in both worlds, and the shipped one was
    right in neither (it announced a downgrade that containment prevents, and named it as
    the outcome even though the phase loop refuses it).
    """
    if shared_is_executable:
        return _NET_POLICY_BODY
    return _NET_POLICY_NOT_EXECUTABLE_PREFIX + _NET_POLICY_BODY


def _money(value: Decimal) -> str:
    return str(value.quantize(_MONEY_Q, rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class AllocationIssue:
    """A single validation finding (doc 13 §10.1, §6.2 error texts)."""

    code: str
    severity: str
    message: str
    field: str | None = None
    composition_item_id: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": str(self.code),
            "severity": str(self.severity),
            "message": self.message,
            "field": self.field,
            "composition_item_id": self.composition_item_id,
        }


@dataclass(frozen=True, slots=True)
class SleeveAmount:
    composition_item_id: str
    equity_share_percent: str
    initial_sleeve_capital: str

    def as_dict(self) -> dict[str, str]:
        return {
            "composition_item_id": self.composition_item_id,
            "equity_share_percent": self.equity_share_percent,
            "initial_sleeve_capital": self.initial_sleeve_capital,
        }


@dataclass(frozen=True, slots=True)
class DerivedAmounts:
    """Server-canonical preview amounts (doc 13 §5.3, §8.3)."""

    currency: str | None
    portfolio_initial_capital: str
    reserved_cash: str
    capital_available: str
    total_allocated: str
    unallocated: str
    active_share_total: str
    sleeves: tuple[SleeveAmount, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "portfolio_initial_capital": self.portfolio_initial_capital,
            "reserved_cash": self.reserved_cash,
            "capital_available": self.capital_available,
            "total_allocated": self.total_allocated,
            "unallocated": self.unallocated,
            "active_share_total": self.active_share_total,
            "sleeves": [s.as_dict() for s in self.sleeves],
        }


@dataclass(frozen=True, slots=True)
class AllocationItemRef:
    """Composition-item availability resolved by the command layer (doc 13 §10.1).

    ``settlement_currency`` is the item's traded-instrument settlement currency,
    resolved impurely by the command layer from the pinned work object -> canonical
    instrument (doc 13 §5.1). ``None`` means "unknown / not resolvable" — the FX
    cross-check is skipped for that item (a difference is never fabricated), other
    layers still surface a missing/unusable pin.
    """

    kind: MainboardItemKind
    available: bool
    settlement_currency: str | None = None


def validate_allocation(
    config: PortfolioAllocationConfigV1,
    *,
    item_refs: dict[str, AllocationItemRef],
) -> tuple[list[AllocationIssue], DerivedAmounts | None]:
    """Return ``(issues, derived)`` for a config (doc 13 §10.1, §14).

    Independent mode (``enabled=false``) is valid and engine-clear: the shared pool
    is not evaluated, so no issues and no derived amounts are produced (§4, §14#2).

    Containment (ADIM 3): while ``domain.allocation.capability`` reports shared
    capital as non-executable, an ENABLED plan leads with a BLOCKER. It is emitted
    FIRST so it is the lead blocker every caller promotes — the Ready Check error
    envelope lifts the leading blocker's remediation, and a user fixing sleeve
    percentages before being told the mode cannot run at all would be wasted work.
    The remaining field checks still run so the plan stays fully diagnosable while
    the draft remains editable and saveable (only the freeze and the RUN are
    refused); the shared-pool derived amounts are still computed, because they are
    what the page previews — they are not a run result.
    """
    if not config.enabled:
        return [], None

    issues: list[AllocationIssue] = []
    # Read ONCE: the containment blocker and the NET notice below must never describe two
    # different worlds within a single validation pass.
    shared_is_executable = shared_allocation_is_executable()
    if not shared_is_executable:
        issues.append(
            AllocationIssue(
                Code.SHARED_MODE_NOT_IN_BUILD,
                Sev.BLOCKER,
                SHARED_ALLOCATION_MESSAGE,
                field=SHARED_ALLOCATION_FIELD_PATH,
            )
        )

    # ---- Shared Capital Pool field checks (§5.1) ---------------------------- #
    capital_ok = config.initial_capital is not None and config.initial_capital.amount > _ZERO
    if not capital_ok:
        issues.append(
            AllocationIssue(
                Code.INITIAL_CAPITAL_INVALID,
                Sev.BLOCKER,
                "Initial Capital must be a decimal greater than 0.",
                field="initial_capital",
            )
        )
    if config.initial_capital is None:
        issues.append(
            AllocationIssue(
                Code.BASE_CURRENCY_INVALID,
                Sev.BLOCKER,
                "A valid Base Currency is required in shared mode.",
                field="initial_capital.currency",
            )
        )
    if config.compounding_mode is None:
        issues.append(
            AllocationIssue(
                Code.COMPOUNDING_MODE_INVALID,
                Sev.BLOCKER,
                "A valid Compounding Mode is required.",
                field="compounding_mode",
            )
        )

    reserve = config.reserve_cash_percent if config.reserve_cash_percent is not None else _ZERO
    reserve_ok = _ZERO <= reserve < _HUNDRED
    if not reserve_ok:
        issues.append(
            AllocationIssue(
                Code.RESERVE_OUT_OF_RANGE,
                Sev.BLOCKER,
                "Reserve Cash must be in the range [0, 100).",
                field="reserve_cash_percent",
            )
        )

    # ---- Portfolio-level rules (cross-item, doc 13 §8.4) -------------------- #
    if config.max_total_exposure_percent is not None and config.max_total_exposure_percent <= _ZERO:
        issues.append(
            AllocationIssue(
                Code.MAX_TOTAL_EXPOSURE_INVALID,
                Sev.BLOCKER,
                "Max Total Exposure must be a percent greater than 0 when set "
                "(it caps total concurrent notional across all items against the pool P0).",
                field="max_total_exposure_percent",
            )
        )
    if config.conflict_policy == ConflictPolicy.NET:
        # BLOCKER, not WARNING, since B0 (signed 2026-08-27). The MESSAGE is unchanged --
        # it is pinned by Decision 3's signature and already ends by telling the caller to
        # choose BLOCK_OPPOSITE or KEEP_SEPARATE, which is what a blocker must say.
        #
        # What this flip does and does NOT do. It makes a STORED NET plan read NOT_READY
        # instead of READY_WITH_WARNINGS (``_readiness_state``) -- that is the drainage
        # signal B3 needs. It does NOT stop a NET row from being written: the only writer
        # of ``plan.conflict_policy`` is ``upsert_allocation_draft`` and that path never
        # consults ``has_blockers`` (a draft is allowed to be invalid). The actual freeze
        # is the token refusal at that write boundary; see Decision 4 / Olcum 6.
        issues.append(
            AllocationIssue(
                Code.CONFLICT_POLICY_NET_V1,
                Sev.BLOCKER,
                _net_policy_warning(shared_is_executable=shared_is_executable),
                field="conflict_policy",
            )
        )

    # ---- Entry checks (§5.2, §10.1) ---------------------------------------- #
    active = [e for e in config.entries if e.active]
    if not active:
        issues.append(
            AllocationIssue(
                Code.NO_ACTIVE_ENTRY,
                Sev.BLOCKER,
                "Shared allocation requires at least one active entry.",
                field="entries",
            )
        )

    seen: set[str] = set()
    share_total = _ZERO
    for entry in active:
        cid = entry.composition_item_id
        if cid in seen:
            issues.append(
                AllocationIssue(
                    Code.DUPLICATE_ACTIVE_ENTRY,
                    Sev.BLOCKER,
                    "An item can have only one active allocation row in V1.",
                    composition_item_id=cid,
                )
            )
            continue
        seen.add(cid)

        ref = item_refs.get(cid)
        if ref is None or not ref.available:
            issues.append(
                AllocationIssue(
                    Code.ITEM_UNAVAILABLE,
                    Sev.BLOCKER,
                    "Selected Mainboard item is unavailable, deleted, or not in this composition.",
                    composition_item_id=cid,
                )
            )
        # Compatibility is judged independently of availability: an item that IS in
        # the composition still cannot take a sleeve unless its kind is allocatable
        # (doc 13 §5.2, §14#8). Unresolvable refs are already blocked above.
        if ref is not None and ref.kind not in ALLOCATABLE_ITEM_KINDS:
            issues.append(
                AllocationIssue(
                    Code.ITEM_KIND_NOT_ALLOCATABLE,
                    Sev.BLOCKER,
                    f"Item kind '{ref.kind}' cannot be allocated a capital sleeve; only "
                    "Strategy, Trading Signal and Trade Log items are allocatable.",
                    composition_item_id=cid,
                )
            )

        share = entry.equity_share_percent
        if share is None or share <= _ZERO:
            issues.append(
                AllocationIssue(
                    Code.ENTRY_SHARE_INVALID,
                    Sev.BLOCKER,
                    "Active entry Equity Share must be greater than 0.",
                    composition_item_id=cid,
                )
            )
        else:
            share_total += share

    if share_total > _HUNDRED:
        issues.append(
            AllocationIssue(
                Code.TOTAL_ALLOCATION_EXCEEDS_100,
                Sev.BLOCKER,
                f"Total allocation is {share_total}%; it cannot exceed 100%.",
                field="entries",
            )
        )
    elif active and share_total > _ZERO and share_total < _HUNDRED:
        issues.append(
            AllocationIssue(
                Code.TOTAL_ALLOCATION_UNDER_100,
                Sev.WARNING,
                f"{share_total}% active share defined; the remaining "
                f"{_HUNDRED - share_total}% stays unallocated and is not auto-borrowed.",
                field="entries",
            )
        )

    if len(active) == 1:
        issues.append(
            AllocationIssue(
                Code.ONE_ACTIVE_SLEEVE,
                Sev.WARNING,
                "Shared allocation has only one active sleeve; portfolio distribution is limited.",
                composition_item_id=active[0].composition_item_id,
            )
        )

    issues.extend(_fx_dependency_issues(config, active, item_refs))

    derived = _derive(config, active) if (capital_ok and reserve_ok) else None
    return issues, derived


def _normalize_currency(value: str | None) -> str:
    return (value or "").strip().upper()


def _fx_dependency_issues(
    config: PortfolioAllocationConfigV1,
    active: list,  # type: ignore[type-arg]
    item_refs: dict[str, AllocationItemRef],
) -> list[AllocationIssue]:
    """Block a mixed-currency pool with no conversion source (doc 13 §5.1, §6.2).

    The Base Currency is the pool/ledger accounting currency; every active item's
    traded-instrument settlement currency must equal it, OR an approved, pinned FX
    conversion dataset must exist. No such dataset entity exists in V1 (the engine
    assumes a single-currency pool, GAP-16), so a resolved mismatch always blocks —
    the system never converts silently. Fail-closed on a KNOWN difference only: an
    unresolved (``None``) settlement currency is skipped (never a fabricated diff),
    and a missing Base Currency is already covered by ``BASE_CURRENCY_INVALID``.
    """
    base = config.initial_capital.currency if config.initial_capital is not None else None
    base_ccy = _normalize_currency(str(base)) if base is not None else ""
    if not base_ccy:
        return []

    issues: list[AllocationIssue] = []
    for entry in active:
        ref = item_refs.get(entry.composition_item_id)
        if ref is None or ref.settlement_currency is None:
            continue
        item_ccy = _normalize_currency(ref.settlement_currency)
        if not item_ccy or item_ccy == base_ccy:
            continue
        issues.append(
            AllocationIssue(
                Code.FX_DEPENDENCY_MISSING,
                Sev.BLOCKER,
                f"Base Currency ({base_ccy}) differs from this item's settlement currency "
                f"({item_ccy}) and no approved pinned FX conversion dataset is available. "
                "The system does not silently convert; attach an approved FX conversion "
                "dataset or align the currencies.",
                field="initial_capital.currency",
                composition_item_id=entry.composition_item_id,
            )
        )
    return issues


def _derive(
    config: PortfolioAllocationConfigV1,
    active: list,  # type: ignore[type-arg]
) -> DerivedAmounts:
    assert config.initial_capital is not None  # capital_ok guaranteed by caller
    p0 = config.initial_capital.amount
    reserve = config.reserve_cash_percent if config.reserve_cash_percent is not None else _ZERO
    r0 = p0 * reserve / _HUNDRED
    a0 = p0 - r0
    if a0 < _ZERO:
        a0 = _ZERO

    sleeves: list[SleeveAmount] = []
    total_allocated = _ZERO
    share_total = _ZERO
    for entry in active:
        share = entry.equity_share_percent
        if share is None or share <= _ZERO:
            continue
        share_total += share
        sleeve = a0 * share / _HUNDRED
        total_allocated += sleeve
        sleeves.append(SleeveAmount(entry.composition_item_id, str(share), _money(sleeve)))

    return DerivedAmounts(
        currency=str(config.initial_capital.currency),
        portfolio_initial_capital=_money(p0),
        reserved_cash=_money(r0),
        capital_available=_money(a0),
        total_allocated=_money(total_allocated),
        unallocated=_money(a0 - total_allocated),
        active_share_total=str(share_total),
        sleeves=tuple(sleeves),
    )


def has_blockers(issues: list[AllocationIssue]) -> bool:
    return any(str(i.severity) == str(Sev.BLOCKER) for i in issues)


def canonical_config(config: PortfolioAllocationConfigV1) -> dict[str, object]:
    """JSON-safe canonical dict (Decimals -> strings via Pydantic JSON mode)."""
    return config.model_dump(mode="json")


def compute_config_hash(config: PortfolioAllocationConfigV1) -> str:
    """Deterministic SHA-256 over the canonical serialization (doc 13 §8.5)."""
    serialized = json.dumps(canonical_config(config), sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "ALLOCATABLE_ITEM_KINDS",
    "AllocationIssue",
    "AllocationItemRef",
    "DerivedAmounts",
    "SleeveAmount",
    "canonical_config",
    "compute_config_hash",
    "has_blockers",
    "validate_allocation",
]
