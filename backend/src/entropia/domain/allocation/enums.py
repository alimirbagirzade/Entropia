"""Portfolio / Equity Allocation domain enums (doc 13 §5, §8.2).

Currency and Compounding Mode wire tokens are the canonical UPPERCASE tokens
exactly as doc 13 §8.2 shows them (``USDT``, ``COMPOUND_PORTFOLIO_EQUITY``); the
``enum_column`` CHECK stores those verbatim so the persisted value round-trips to
the documented payload without a mapping layer. (This intentionally deviates from
the lowercase Mainboard-enum convention because these are validated client inputs
whose wire form is fixed by the page contract.) ``item_type`` reuses
``MainboardItemKind`` — it is server-DERIVED from the composition item and never
trusted from the request (§8.2).
"""

from __future__ import annotations

from enum import StrEnum


class AllocationCurrency(StrEnum):
    """Base currency of the shared capital pool / portfolio ledger (doc 13 §5.1)."""

    USD = "USD"
    USDT = "USDT"
    EUR = "EUR"
    TRY = "TRY"


class CompoundingMode(StrEnum):
    """How sleeve caps evolve across valuation points (doc 13 §5.1, §8.3).

    ``Fixed Item Notional`` is NOT a V1 option (doc 13 §6).
    """

    COMPOUND_PORTFOLIO_EQUITY = "COMPOUND_PORTFOLIO_EQUITY"
    FIXED_INITIAL_PORTFOLIO_CAPITAL = "FIXED_INITIAL_PORTFOLIO_CAPITAL"


class CrossItemConflictPolicy(StrEnum):
    """Portfolio-level policy for OPPOSING same-instrument signals ACROSS composition
    items (the cross-item counterpart of doc 02's per-strategy Conflict Handling;
    doc 13 §8.4 step 6 — a blocked item's share is never auto-transferred).

    ``KEEP_SEPARATE`` is the pre-rules behaviour (each item replays independently).
    ``BLOCK_OPPOSITE`` blocks a later-pinned item's entry while an earlier-pinned
    item holds the opposite direction on the same instrument.

    ``NET`` (offsetting the aggregate position) HAS NO CANONICAL DEFINITION, and
    that — not the missing clock — is why it does not run. Neither doc 13 nor
    Master Ref Modül 11 §6.3 states a netting price, position custody, fee
    attribution, realized-PnL attribution or margin treatment for an offset pair;
    the five are enumerated in ``domain/backtest/execution/arbitration.py`` under
    ``NET_UNDEFINED_SEMANTICS``. The two engines therefore disagree about the
    value: the V1 sequential engine downgrades it to BLOCK_OPPOSITE and discloses
    the downgrade (validation warning + L4 engine warning, never silent), while
    the unified-clock phase loop REFUSES a NET run outright rather than label a
    block as netting. Neither happens while ``SHARED_ALLOCATION_STATUS`` is
    ``future_dev``, because no shared plan reaches an engine at all.

    The value is retained for now on purpose: removing it is a migration over the
    persisted ``portfolio_allocation_plan.conflict_policy`` CHECK, decided as
    option `B` and scheduled before `C9`
    (``docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md``, GH #544).
    """

    NET = "NET"
    BLOCK_OPPOSITE = "BLOCK_OPPOSITE"
    KEEP_SEPARATE = "KEEP_SEPARATE"


class AllocationIssueSeverity(StrEnum):
    """A validation issue either blocks a plan revision or only warns (doc 13 §10.1)."""

    BLOCKER = "blocker"
    WARNING = "warning"


class AllocationIssueCode(StrEnum):
    """Machine codes surfaced by allocation validation (doc 13 §10.1, §14)."""

    INITIAL_CAPITAL_INVALID = "INITIAL_CAPITAL_INVALID"
    BASE_CURRENCY_INVALID = "BASE_CURRENCY_INVALID"
    COMPOUNDING_MODE_INVALID = "COMPOUNDING_MODE_INVALID"
    RESERVE_OUT_OF_RANGE = "RESERVE_OUT_OF_RANGE"
    NO_ACTIVE_ENTRY = "NO_ACTIVE_ENTRY"
    ENTRY_SHARE_INVALID = "ENTRY_SHARE_INVALID"
    TOTAL_ALLOCATION_EXCEEDS_100 = "TOTAL_ALLOCATION_EXCEEDS_100"
    TOTAL_ALLOCATION_UNDER_100 = "TOTAL_ALLOCATION_UNDER_100"
    DUPLICATE_ACTIVE_ENTRY = "DUPLICATE_ACTIVE_ENTRY"
    ITEM_UNAVAILABLE = "ITEM_UNAVAILABLE"
    ONE_ACTIVE_SLEEVE = "ONE_ACTIVE_SLEEVE"
    # An active item settles in a currency other than the Base Currency and no
    # approved, pinned FX conversion dataset is available to convert it (doc 13
    # §5.1, §6.2 "Error - FX dependency", §10.1). The system never silently
    # converts — cross-currency pooling blocks fail-closed until a conversion
    # source exists (mirrors the engine GAP-16 single-currency assumption).
    FX_DEPENDENCY_MISSING = "FX_DEPENDENCY_MISSING"
    # A set Max Total Exposure must be a positive percent of the shared pool P0 —
    # a non-positive cap can never admit an entry and is a misconfiguration, not a
    # tradable plan (portfolio-level rules slice).
    MAX_TOTAL_EXPOSURE_INVALID = "MAX_TOTAL_EXPOSURE_INVALID"
    # Pre-disclosure that the chosen NET policy has no canonical definition, so the
    # two engines treat it differently (sequential downgrades to BLOCK_OPPOSITE, the
    # phase loop refuses) and containment means neither runs today. The wire token
    # keeps its ``_V1`` spelling: it is a shipped machine code and renaming it would
    # break every caller for a spelling (O-31 precedent). Text: ``rules.py``
    # ``_net_policy_warning``; decision: G14 / GH #544.
    CONFLICT_POLICY_NET_V1 = "CONFLICT_POLICY_NET_V1"
    # An active entry points at a composition item whose kind is not allocatable.
    # doc 13 §5.2 ("selected item ... must be compatible") and §14#8 name the
    # allocatable set exactly: Strategy, Trading Signal, Trade Log. Today
    # ``MainboardItemKind`` holds only those three, so the guard was IMPLICIT —
    # nothing read the resolved kind. This code makes it explicit so a future
    # non-allocatable kind fails closed instead of being silently allocated a
    # capital sleeve (I-03).
    ITEM_KIND_NOT_ALLOCATABLE = "ITEM_KIND_NOT_ALLOCATABLE"
    # Containment (ADIM 3): shared capital allocation does not EXECUTE in this build.
    # Doc 13 §8.3/§8.4/§13 require ONE portfolio valuation snapshot per timestamp that
    # every active item sizes against; the engine instead replays each item
    # independently and folds the finished runs in pin order, so the composite equity
    # curve is not time-ordered and the portfolio drawdown is wrong. The single source
    # of truth for the status, message, remediation and removal condition is
    # ``domain/allocation/capability.py`` — never restate them at a call site.
    SHARED_MODE_NOT_IN_BUILD = "SHARED_MODE_NOT_IN_BUILD"


__all__ = [
    "AllocationCurrency",
    "AllocationIssueCode",
    "AllocationIssueSeverity",
    "CompoundingMode",
    "CrossItemConflictPolicy",
]
