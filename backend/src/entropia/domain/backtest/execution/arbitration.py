"""Cross-item conflict and capacity arbitration at ONE valuation point (ADR 0002 §9, P5/P6b).

Phases P4 and P6b already have homes: ``execution/intents.py`` types what each item WANTS
and ``execution/portfolio_ledger.py`` answers what ONE item may deploy. Neither can answer
the question that only exists once the pool is genuinely shared — *what happens when two
items want incompatible things at the same instant, and when several affordable orders are
jointly unaffordable*. That question is this module, and nothing else is.

It deliberately does NOT:

* run the phase loop or drive the clock — ``run_portfolio`` is the phase-loop slice. This
  module is a pure function of ``(frozen ledger, published snapshot, intents, pinned
  profiles, policy)``;
* book anything. It writes no equity, opens no position and mutates no ledger field. It is
  called while the ledger is FROZEN (ADR §8.1) and asserts that, so an arbitration result
  can never be produced against an ``E(t)`` a sibling's fill has already moved;
* define ``NET``. Canon defines no netting semantics at all, so ``NET`` is **refused**, not
  downgraded — see :data:`NET_SUPPORT_STATUS`;
* touch Result attribution, the manifest, ``ENGINE_VERSION`` or the containment flag. Every
  decision it produces is a value; whether and how a Result records it is a later slice.

**Nothing in production imports this module.** As with the clock, the intent layer and the
shared ledger, the rollback is "delete the module": ``run_engine`` keeps its signature *and*
its semantics (ADR §3.2), so no golden digest, ``ENGINE_VERSION`` or ``execution_key`` moves
because this file exists. The shipped sequential conflict gate
(``engine.py:1441-1447`` + ``execution/rules.py::conflicts_with_prior``) is untouched and
still behaves exactly as it did.

Design notes that are contracts, not taste
------------------------------------------
**A held position always wins; a new intent never displaces it.** The shipped rule is
forward-only — *"an EARLIER-pinned item holds the opposite direction, so the LATER-pinned
item's entry is blocked"* (``CrossItemConflictPolicy`` docstring) — because the sequential
engine replays items one after another and physically cannot see a later item's position
while simulating an earlier one. Under a merged axis it can, and the pin-order half of that
sentence stops being a rule and becomes an artifact of the old loop (ADR §12 retires it at
this slice). What survives is the part canon actually states: Modül 11 §6.3 limits *"iki
itemin ayni pazarda ayni anda ... uyumsuz pozisyon acmasini"* — opening. Closing a
sibling's open position to make room is not among the outcomes canon offers, and doc 13 §8.3
forbids force-rebalancing an open position outright. So the held side is never the one that
gives way, whatever its pin ordinal.

**Between two intents at the SAME tick, the lower ``(pin_ordinal, item_id)`` is admitted.**
This is the only place a tie-break is needed at P5, and it is the ADR §4.4 tie-break applied
verbatim — ``pin_ordinal`` is the manifest's deterministic ``(root_id,
selected_revision_id)`` sort, never DOM order, never arrival order (doc 13 §13). It is
*symmetric* in the sense removal condition #4 requires: permuting the inputs cannot change
the outcome, because the order is read from the pinned profile and not from the sequence the
caller happened to build.

**A blocked item's capacity is never given to anybody.** The contention loop only ever
SUBTRACTS what an admitted order commits; there is no branch that adds a blocked item's
sleeve, share or headroom to a sibling. That is the structural form of doc 13 §8.4 step 6 /
§13 and Modül 11 §6.3, and
``test_a_blocked_items_capacity_is_never_handed_to_a_sibling`` checks it the only way that
means anything — the sibling's grant is identical with and without the blocked item present.

**Caps clamp; solvency rejects.** ``allowed_size = min(desired, sleeve, item risk limits,
solvency)`` (doc 13 §8.3) is the ledger's own ``resolve_capacity``. This module adds the one
thing a per-item question cannot see: the capital its siblings have already committed *at
this same tick*. The ledger is frozen, so ``available_capital`` reads the same figure for
every item; without a running tally two items would each be granted the whole pool. The
tally is therefore subtracted from the solvency headroom and from the portfolio exposure
cap. When what is left is short, the order is **rejected whole** — Modül 11 §5.3:
*"engine orderi reddeder, kismi fill veya sessiz borrow yapmaz"*. A ``capped`` outcome comes
only from the three CAP layers, never from solvency, and ``capped`` is a smaller ADMITTED
size, not a partially filled order.

**No new vocabulary.** Every reason this layer emits is a token the shipped engine or the
shared ledger already writes (:data:`ARBITRATION_REASONS`), and a test asserts the set is
closed. A cross-item block reads ``portfolio_conflict_blocked`` — the engine's own
(``engine.py:1446``) — with the *counterparty* and *how the tie broke* in the diagnostics,
rather than a second spelling of the same finding.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Literal

from entropia.domain.allocation.enums import CrossItemConflictPolicy
from entropia.domain.backtest.execution.constants import _ZERO
from entropia.domain.backtest.execution.intents import (
    MANDATORY_KINDS,
    ItemIntent,
    PortfolioSnapshot,
)
from entropia.domain.backtest.execution.portfolio_ledger import (
    EXPOSURE_CONSTRAINT,
    LEDGER_INSOLVENT,
    LEDGER_LAYER_REASONS,
    MAX_POSITION_CONSTRAINT,
    PORTFOLIO_MAX_TOTAL_EXPOSURE,
    SLEEVE_CONSTRAINT,
    SLEEVE_ZERO_CAPACITY,
    SOLVENCY_CONSTRAINT,
    CapacityDecision,
    PortfolioLedger,
)

# Pins the arbitration RULE SET and the tie-break, exactly as ``CLOCK_POLICY_VERSION`` pins
# the axis and ``LEDGER_POLICY_VERSION`` pins the capital arithmetic. ADR §10.3 places the
# manifest field ``arbitration_policy_version`` in the containment-lift slice; this constant
# exists so the contract it names has one home from its first line, not so it ships early.
ARBITRATION_POLICY_VERSION = "arbitration-policy-v1"

_ARBITRATION_IDENTITY_NAMESPACE = "entropia.backtest.portfolio.arbitration"

PORTFOLIO_CONFLICT_BLOCKED = "portfolio_conflict_blocked"
"""The shipped engine's own cross-item block token (``engine.py:1446``), reused verbatim so a
unified-clock block reads in the same vocabulary as a sequential one."""

CONFLICT_SYMBOL_UNKNOWN_GATE = "portfolio_conflict_symbol_unknown_fail_closed"
"""The shipped L4 warning raised when an instrument identity is missing on either side
(``execution/output.py:179``). Carried here as a DIAGNOSTIC flag, never as a reason: the
finding is still ``portfolio_conflict_blocked``; this only records that it was reached
fail-closed rather than on a proven instrument match."""

ARBITRATION_REASONS: frozenset[str] = frozenset(
    {PORTFOLIO_CONFLICT_BLOCKED, SLEEVE_ZERO_CAPACITY, PORTFOLIO_MAX_TOTAL_EXPOSURE}
    | LEDGER_LAYER_REASONS
)
"""Every reason this layer can emit — and it introduces **none of its own**.

The clock, the intent layer and the ledger each had to name states that only exist once
there is a shared axis. Arbitration does not: a cross-item block is the engine's
``portfolio_conflict_blocked`` and every capacity refusal is the ledger's own token. What is
new here is *which item* is refused, not *what kind of refusal exists*, so a new vocabulary
would only give reviewers two names for one finding."""

ConflictOutcome = Literal["admitted", "capped", "blocked", "rejected", "not_actionable"]
"""``blocked`` is P5 (a sibling's incompatible position/intent), ``rejected`` is P6b (no
capacity), ``capped`` is a smaller admitted size from a CAP layer, and ``not_actionable``
records an intent that asked for no order — emitted, never dropped (ADR §6 rule 5)."""

ConflictSource = Literal["held_position", "same_tick_intent"]
"""Which side of the tick the counterparty was on. A ``held_position`` conflict is decided by
the position (it never gives way); a ``same_tick_intent`` conflict is decided by the pin-order
tie-break."""


# ------------------------------------------------------------------- NET capability state

NET_SUPPORT_STATUS = "undefined_in_canon"
"""``NET`` does not execute here, and is not substituted by anything that does.

The shipped sequential engine runs ``NET`` conservatively as ``BLOCK_OPPOSITE`` and discloses
the downgrade (``engine.py:862-871``, ``CONFLICT_POLICY_NET_V1``). That downgrade is *not*
carried forward: presenting a block as if it were netting would advertise a semantics canon
has never defined, which is precisely the finding of GH #544. ADR §9.4 says the unified clock
removes NET's stated excuse without supplying its meaning — so this layer **refuses** a NET
run (:class:`UnsupportedConflictPolicyError`) instead of quietly executing a different
policy. Refusing produces no Result at all, which is strictly safer than producing one whose
policy label does not describe what ran."""

NET_UNDEFINED_SEMANTICS: tuple[str, ...] = (
    "netting price — at what price two opposing item positions offset",
    "position custody — which item's book holds the netted position, and what the other holds",
    "fee attribution — whether the offset charges one commission, two, or none",
    "realized PnL attribution — how the netted result is split between the two items",
    "margin/collateral — what committed capital a netted pair ties up (Master Ref §10.2 "
    "delegates cross-margin to a portfolio risk model that does not exist)",
)
"""The five things that must be defined before ``NET`` can be implemented (GH #544 §"What
must be decided"; ADR §9.4, §9.5). Each is a product decision, not an engineering choice —
any of them guessed here would produce numbers a user could not audit against canon."""

NET_TRACKING_ISSUE = "GH #544"

NET_MESSAGE = (
    "The NET cross-item conflict policy has no canonical definition: neither doc 13 nor "
    "Master Ref Modül 11 §6.3 defines a netting price, position custody, fee attribution, "
    "realized-PnL attribution or margin treatment for an offset pair. The unified-clock "
    "co-simulation removes NET's stated dependency but supplies none of that meaning."
)

NET_REMEDIATION = (
    "Choose BLOCK_OPPOSITE (an opposing entry is blocked and traced) or KEEP_SEPARATE (both "
    "items hold their own books against the shared pool). NET re-opens only when its five "
    f"undefined semantics are decided and recorded ({NET_TRACKING_ISSUE})."
)


# ---------------------------------------------------------------------- OD-3 disclosure

CONTENTION_SELECTION_POLICY = "pin_order_admission"
"""How several jointly-insolvent intents are selected between: admit in ``(pin_ordinal,
item_id)`` order until the pool's committable capital is exhausted, then reject the rest
whole."""

CONTENTION_SELECTION_STATUS = "recommended_pending_approval"
"""**OD-3 is open.** Canon decides the RESPONSE to a solvency shortfall — reject, never a
partial fill, never a borrow (Modül 11 §5.3) — and this module implements exactly that. It
does not decide *which* of several individually-affordable intents is refused; ADR §13 OD-3
records that gap, recommends this policy and flags the alternative a reviewer may prefer
(reject ALL competing intents, which has no systematic ordering advantage at the cost of
refusing trades that could have filled). The recommendation is implemented and LABELLED as
such rather than silently adopted: :data:`CONTENTION_SELECTION_POLICY` travels in every
report, so a Result produced under it can always be told from one produced under a different
resolution."""

CONTENTION_SELECTION_NOTE = (
    "OD-3 (ADR 0002 §13) is unresolved. Admission order is the manifest-pinned "
    "(pin_ordinal, item_id) tie-break the containment's own removal condition #4 already "
    "commits to; the alternative under review is a fully symmetric reject-all."
)


# ----------------------------------------------------------------------- the policy table


@dataclass(frozen=True, slots=True)
class ConflictPolicyRule:
    """One row of the cross-item conflict policy table — what a policy DOES, and its status.

    ``shares_capital`` is ``True`` for every row and is stated rather than assumed: the
    policy governs *positions*, never the pool. KEEP_SEPARATE keeps separate position books;
    it does not hand an item a private wallet, so the sleeve cap, the portfolio exposure cap
    and the solvency limit apply under it exactly as under BLOCK_OPPOSITE (Modül 11 §6.1)."""

    policy: str
    supported: bool
    opposite_same_instrument: Literal["allowed", "blocked", "undefined"]
    same_direction_same_instrument: Literal["allowed", "blocked", "undefined"]
    separate_position_books: bool
    shares_capital: bool
    canon: str
    undefined_semantics: tuple[str, ...] = ()


CONFLICT_POLICY_TABLE: Mapping[str, ConflictPolicyRule] = MappingProxyType(
    {
        CrossItemConflictPolicy.KEEP_SEPARATE.value: ConflictPolicyRule(
            policy=CrossItemConflictPolicy.KEEP_SEPARATE.value,
            supported=True,
            opposite_same_instrument="allowed",
            same_direction_same_instrument="allowed",
            separate_position_books=True,
            shares_capital=True,
            canon=(
                "The pre-rules behaviour: no cross-item position constraint. Modül 11 §6.1's "
                "cap layers still apply — a separate book is not a separate pool."
            ),
        ),
        CrossItemConflictPolicy.BLOCK_OPPOSITE.value: ConflictPolicyRule(
            policy=CrossItemConflictPolicy.BLOCK_OPPOSITE.value,
            supported=True,
            opposite_same_instrument="blocked",
            same_direction_same_instrument="allowed",
            separate_position_books=True,
            shares_capital=True,
            canon=(
                "Modül 11 §6.3: conflict rules may limit two items opening opposing positions "
                "on the same market at the same time; the blocked item's share is never "
                "transferred (doc 13 §8.4 step 6, §13)."
            ),
        ),
        CrossItemConflictPolicy.NET.value: ConflictPolicyRule(
            policy=CrossItemConflictPolicy.NET.value,
            supported=False,
            opposite_same_instrument="undefined",
            same_direction_same_instrument="undefined",
            separate_position_books=True,
            shares_capital=True,
            canon=(
                "No canonical definition exists. Doc 13's own draft-write contract carries no "
                "conflict_policy field at all; the enum value arrived with migration "
                "0035_portfolio_rules. ADR §9.4, GH #544."
            ),
            undefined_semantics=NET_UNDEFINED_SEMANTICS,
        ),
    }
)
"""Every cross-item conflict policy, what it does, and whether it executes.

One table, so no call site re-derives a policy's behaviour from a string comparison. Keyed by
the canonical ``CrossItemConflictPolicy`` wire token (the value persisted in the plan config
and pinned into the manifest)."""


# ------------------------------------------------------------------------------- refusals


class ArbitrationError(ValueError):
    """Arbitration cannot be performed on the inputs as given.

    Mirrors ``clock.ClockAxisError`` / ``intents.IntentError`` / ``portfolio_ledger.
    LedgerError``: a ``ValueError`` the worker turns into a failed run (ADR §11 — a run that
    cannot resolve a phase fails rather than skipping it). Every subclass fails closed."""


class UnsupportedConflictPolicyError(ArbitrationError):
    """The pinned conflict policy cannot be executed honestly.

    Two cases, both fail-closed. ``NET`` is undefined in canon (:data:`NET_MESSAGE`) and is
    refused rather than substituted. An UNKNOWN token — a tampered, foreign or future
    snapshot — is refused too: the shipped sequential engine fails such a token closed *to
    blocking*, which is a degraded execution of a policy nobody can name, and producing a
    Result under it would label the run with a policy that never ran."""


class MandatoryIntentNotArbitrableError(ArbitrationError):
    """A P3 mandatory intent was handed to P5.

    Stops, exits, funding and fees resolve BEFORE the valuation point (ADR §6 rule 4; Modül 11
    §5.2), so by the time arbitration runs they are already in the ledger. Arbitrating one
    would either apply it twice or let a sibling veto a mandatory protective exit — and canon
    offers no outcome in which a stop is blocked by another item's intent."""


class LedgerNotFrozenError(ArbitrationError):
    """Arbitration was attempted outside the frozen window.

    P5 and P6b sit between ``PV`` and ``P7`` (ADR §8.1). Running them against a writable
    ledger would let one item's booking move ``E(t)``, the sleeve headroom and the solvency
    headroom under the siblings still being arbitrated — the per-item drift the unified clock
    exists to remove, arriving through the back door."""


class MismatchedTickError(ArbitrationError):
    """An intent, the snapshot and the frozen ledger do not all name the same instant."""


class UnknownArbitrationItemError(ArbitrationError):
    """An intent whose item has no pinned arbitration profile.

    Priority and instrument identity are read from the run manifest's pinned items. An item
    without a profile has no ordinal to break ties with and no instrument to compare, so it
    is refused rather than arbitrated on a guess."""


class DuplicateIntentError(ArbitrationError):
    """Two intents for one item at one tick. The engine keeps ONE position per item
    (``engine.py:1146``); a second intent would be silently arbitrated against its own twin."""


# --------------------------------------------------------------------------- value types


@dataclass(frozen=True, slots=True)
class ItemArbitrationProfile:
    """One item's arbitration identity, as the run manifest froze it.

    ``pin_ordinal`` is the item's index in ``manifest._pinned_items``' deterministic
    ``(root_id, selected_revision_id)`` order — the priority this module breaks ties with.
    ``instrument_id`` is the pinned data source's canonical instrument (the value the worker
    already reads as ``prepared.config.data.instrument_id``,
    ``jobs/backtest_engine.py:316``), NOT a live registry join.

    Both matter for the same reason: a plan edited after the run must not change how an old
    Result's conflicts were resolved (doc 13 §11.1). Everything here comes from the immutable
    snapshot, so replaying a historical report cannot consult today's composition.

    ``instrument_id`` may be ``None``. That is not a licence to ignore the item: an unknown
    identity on either side counts as potentially the SAME instrument, exactly as the shipped
    gate reads it (``execution/rules.py::conflicts_with_prior``) — an unnameable thing can
    never RULE OUT a conflict."""

    item_id: str
    pin_ordinal: int
    instrument_id: str | None = None

    @property
    def priority(self) -> tuple[int, str]:
        """The ADR §4.4 tie-break, as one comparable value so no call site rebuilds it."""
        return (self.pin_ordinal, self.item_id)


@dataclass(frozen=True, slots=True)
class ArbitrationDecision:
    """What one item may do at this valuation point, and exactly why.

    ``limits`` carries every capacity layer's headroom whether or not it bound, so a reviewer
    reading a capped grant sees the layer that bound it *and* the ones that did not.
    ``diagnostics`` is measurement and provenance only — it never carries a threshold and is
    never read back as a decision."""

    item_id: str
    pin_ordinal: int
    outcome: ConflictOutcome
    kind: str
    direction: str | None
    instrument_id: str | None
    requested_units: Decimal
    granted_units: Decimal
    granted_notional: Decimal
    reason: str | None
    binding_constraint: str | None
    counterparty_item_id: str | None = None
    conflict_source: ConflictSource | None = None
    limits: Mapping[str, Decimal] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "limits", MappingProxyType(dict(self.limits)))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))

    @property
    def is_admitted(self) -> bool:
        return self.outcome in ("admitted", "capped")


@dataclass(frozen=True, slots=True)
class ArbitrationReport:
    """The whole tick's arbitration, in pinned priority order.

    ``identity`` is a deterministic digest of the decisions: two runs of the same tick produce
    the same string, and any change of outcome, grant or ordering changes it. That is what
    makes "conflict outcomes are replayable" checkable over the report alone, without holding
    on to the ledger that produced it.

    ``committed_notional`` is the capital this tick's admissions newly commit — the running
    tally the contention loop subtracts. ``released_capacity_reallocated`` is ``False``,
    always, and is published rather than assumed: it is the machine-readable form of doc 13
    §8.4 step 6 (*a blocked item's share is never transferred*)."""

    t_ms: int
    policy: str
    snapshot_identity: str
    decisions: tuple[ArbitrationDecision, ...]
    committed_notional: Decimal
    identity: str = field(default="", compare=False, repr=False)
    policy_version: str = ARBITRATION_POLICY_VERSION
    selection_policy: str = CONTENTION_SELECTION_POLICY
    selection_status: str = CONTENTION_SELECTION_STATUS
    released_capacity_reallocated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity", self._compute_identity())

    def by_item(self, item_id: str) -> ArbitrationDecision:
        for decision in self.decisions:
            if decision.item_id == item_id:
                return decision
        raise UnknownArbitrationItemError(f"Item '{item_id}' was not arbitrated at this tick.")

    @property
    def admitted(self) -> tuple[ArbitrationDecision, ...]:
        return tuple(d for d in self.decisions if d.is_admitted)

    @property
    def refused(self) -> tuple[ArbitrationDecision, ...]:
        """Blocked and rejected together — what a decision trace must show, never drop."""
        return tuple(d for d in self.decisions if d.outcome in ("blocked", "rejected"))

    def _compute_identity(self) -> str:
        digest = hashlib.sha256()
        digest.update(_ARBITRATION_IDENTITY_NAMESPACE.encode("utf-8"))
        for part in (
            self.policy_version,
            self.selection_policy,
            self.policy,
            str(self.t_ms),
            self.snapshot_identity,
        ):
            digest.update(b"\x1f")
            digest.update(part.encode("utf-8"))
        for decision in self.decisions:
            digest.update(b"\x1f")
            digest.update(
                "|".join(
                    (
                        decision.item_id,
                        str(decision.pin_ordinal),
                        decision.outcome,
                        decision.reason or "",
                        decision.binding_constraint or "",
                        decision.counterparty_item_id or "",
                        _canonical_decimal(decision.granted_units),
                        _canonical_decimal(decision.granted_notional),
                    )
                ).encode("utf-8")
            )
        return digest.hexdigest()


def _canonical_decimal(value: Decimal) -> str:
    """One spelling per NUMBER, so a digest identifies an outcome and not a format.

    Same rule as ``intents._canonical_decimal``: ``Decimal("0.00")`` and ``Decimal("0")`` are
    the same grant and must hash the same."""
    if value == _ZERO:
        return "0"
    return str(value.normalize())


# ------------------------------------------------------------------------------ internals


def resolve_policy(token: str | None) -> ConflictPolicyRule:
    """The policy table row for a pinned token; fail closed on anything unexecutable.

    ``None`` / blank is the absence of a cross-item rule, which is KEEP_SEPARATE by
    definition — the same reading ``engine.resolve_portfolio_rules`` uses when it returns
    ``None`` for an unset policy. Anything the table cannot execute raises."""
    normalized = (token or "").strip().upper() or CrossItemConflictPolicy.KEEP_SEPARATE.value
    rule = CONFLICT_POLICY_TABLE.get(normalized)
    if rule is None:
        raise UnsupportedConflictPolicyError(
            f"Unknown cross-item conflict policy {token!r}. A policy nobody can name cannot "
            "be executed, and executing a different one under its label would mislabel the "
            f"Result. Known policies: {sorted(CONFLICT_POLICY_TABLE)}."
        )
    if not rule.supported:
        raise UnsupportedConflictPolicyError(
            f"{NET_MESSAGE} Undefined: {'; '.join(rule.undefined_semantics)}. {NET_REMEDIATION}"
        )
    return rule


def _may_be_same_instrument(left: str | None, right: str | None) -> tuple[bool, bool]:
    """``(may_be_the_same, identity_unknown)`` — fail closed on an unknown identity.

    Verbatim the shipped reading (``execution/rules.py::conflicts_with_prior``): two KNOWN and
    different instruments cannot conflict; anything else may, because an unnameable
    instrument can never rule a conflict OUT."""
    own = (left or "").strip()
    other = (right or "").strip()
    if own and other:
        return own == other, False
    return True, True


def _opposes(left: str | None, right: str | None) -> bool:
    return left in ("long", "short") and right in ("long", "short") and left != right


def _profile_for(
    intent: ItemIntent, profiles: Mapping[str, ItemArbitrationProfile]
) -> ItemArbitrationProfile:
    profile = profiles.get(intent.item_id)
    if profile is None:
        raise UnknownArbitrationItemError(
            f"Item '{intent.item_id}' has no pinned arbitration profile; its priority and "
            "instrument would have to be guessed."
        )
    if profile.pin_ordinal != intent.identity.pin_ordinal:
        raise UnknownArbitrationItemError(
            f"Item '{intent.item_id}' is pinned at ordinal {profile.pin_ordinal} but its "
            f"intent claims {intent.identity.pin_ordinal}; priority must come from ONE pinned "
            "order, not from whichever half of the input the caller filled in last."
        )
    return profile


def _validate(
    *,
    ledger: PortfolioLedger,
    snapshot: PortfolioSnapshot,
    intents: Sequence[ItemIntent],
    profiles: Mapping[str, ItemArbitrationProfile],
) -> list[tuple[ItemArbitrationProfile, ItemIntent]]:
    """Refuse every input that would make the result meaningless, then order it.

    Ordering is by the PINNED priority, never by the sequence the caller supplied — which is
    what makes "item order does not change the result" (doc 13 §13, ADR A4) structural."""
    if not ledger.is_frozen:
        raise LedgerNotFrozenError(
            "Arbitration runs between PV and P7 (ADR §8.1); call publish_snapshot() first so "
            "every item is arbitrated against one frozen E(t)."
        )
    seen: set[str] = set()
    pairs: list[tuple[ItemArbitrationProfile, ItemIntent]] = []
    for intent in intents:
        if intent.phase == "P3" or intent.kind in MANDATORY_KINDS:
            # Both halves, not just the phase tag: a hand-built intent could carry
            # ``phase="P4"`` with ``kind="exit"``, and an exit that reached P5 would be
            # conflict-checked and re-sized as if it were a discretionary order.
            raise MandatoryIntentNotArbitrableError(
                f"Item '{intent.item_id}' offered a mandatory '{intent.kind}' "
                f"(phase {intent.phase}) to arbitration; mandatory events are resolved before "
                "the valuation point and are never subject to a sibling's veto."
            )
        if intent.t_ms != snapshot.t_ms:
            raise MismatchedTickError(
                f"Item '{intent.item_id}' is at t_ms={intent.t_ms} but the snapshot was "
                f"published at t_ms={snapshot.t_ms}."
            )
        if intent.snapshot_identity != snapshot.identity:
            raise MismatchedTickError(
                f"Item '{intent.item_id}' was formed against another valuation; every item at "
                "a tick must be arbitrated against the ONE snapshot it sized itself with."
            )
        if intent.item_id in seen:
            raise DuplicateIntentError(
                f"Item '{intent.item_id}' has two intents at t_ms={snapshot.t_ms}."
            )
        seen.add(intent.item_id)
        pairs.append((_profile_for(intent, profiles), intent))
    pairs.sort(key=lambda pair: pair[0].priority)
    return pairs


def _decision_base(profile: ItemArbitrationProfile, intent: ItemIntent) -> dict[str, Any]:
    """The fields every decision carries whatever the outcome, built in ONE place.

    Both passes construct a decision for the same item, and a field spelled differently in
    one of them would make two records of one item disagree about what it asked for."""
    return {
        "item_id": intent.item_id,
        "pin_ordinal": profile.pin_ordinal,
        "kind": intent.kind,
        "direction": intent.direction,
        "instrument_id": profile.instrument_id,
        "requested_units": intent.desired_size,
    }


def _priority_of(item_id: str, profiles: Mapping[str, ItemArbitrationProfile]) -> tuple[int, str]:
    """The pinned priority of an item the ledger holds a position for.

    A holder with no profile sorts LAST rather than raising: it is not the item being
    arbitrated, so refusing the whole tick over it would fail the run for a counterparty that
    only ever needs a stable position in a scan. It still participates in the conflict check —
    an unnameable holder cannot rule a conflict out."""
    profile = profiles.get(item_id)
    return profile.priority if profile is not None else (len(profiles) + 1, item_id)


def _conflict_against(
    *,
    profile: ItemArbitrationProfile,
    intent: ItemIntent,
    ledger: PortfolioLedger,
    profiles: Mapping[str, ItemArbitrationProfile],
    earlier: Sequence[tuple[ItemArbitrationProfile, ItemIntent]],
) -> tuple[str, ConflictSource, bool] | None:
    """The counterparty that blocks this intent, or ``None``.

    Held positions are checked FIRST and win outright — closing a sibling's position to make
    room is not an outcome canon offers (doc 13 §8.3 forbids force-rebalancing). Same-tick
    intents are checked second, and only those with a STRICTLY earlier pinned priority can
    block, so exactly one side of a simultaneous pair gives way and the loser is a function of
    the manifest rather than of the input order.

    The held-position scan is ordered by the counterparty's own pinned priority, NOT by
    ``ledger.positions``' insertion order. Insertion order is a function of when each position
    happened to be opened during the replay, and while that is itself deterministic it is not
    the manifest — an intent opposed by two holders would name whichever one traded first.
    ADR §4.4 forbids letting dict iteration decide an outcome, and the reported counterparty
    *is* an outcome: it is what the decision trace attributes the block to."""
    for held_item, position in sorted(
        ledger.positions.items(), key=lambda pair: _priority_of(pair[0], profiles)
    ):
        if held_item == intent.item_id:
            continue
        if not _opposes(intent.direction, position.direction):
            continue
        held_profile = profiles.get(held_item)
        same, unknown = _may_be_same_instrument(
            profile.instrument_id, held_profile.instrument_id if held_profile else None
        )
        if same:
            return held_item, "held_position", unknown
    for other_profile, other_intent in earlier:
        if not other_intent.is_actionable or not _opposes(intent.direction, other_intent.direction):
            continue
        same, unknown = _may_be_same_instrument(profile.instrument_id, other_profile.instrument_id)
        if same:
            return other_profile.item_id, "same_tick_intent", unknown
    return None


def _price_of(intent: ItemIntent) -> Decimal:
    """The price this order would deploy at — the intent's own, never re-derived.

    ``effective_price`` is the spread/slippage-adjusted fill the sizing chain already used
    (``costs._effective_fill``); ``reference_price`` is the fallback for an intent whose kind
    carries no fill adjustment. ``0`` means unpriceable, and the ledger refuses it rather than
    inventing a price (``UNPRICEABLE_CAPACITY``)."""
    if intent.effective_price is not None:
        return intent.effective_price
    return intent.reference_price if intent.reference_price is not None else _ZERO


def _decide_capacity(
    *,
    ledger: PortfolioLedger,
    snapshot: PortfolioSnapshot,
    intent: ItemIntent,
    committed: Decimal,
    max_position_notional: Decimal | None,
    max_total_exposure_notional: Decimal | None,
) -> tuple[CapacityDecision, bool]:
    """One item's P6b answer, net of what this tick's earlier admissions already committed.

    Returns ``(decision, contended)``. ``contended`` marks the case the ledger alone cannot
    see: the order fits the pool as the frozen ledger reads it, but not once a sibling's
    admission at this same tick is counted. That is the OD-3 case, and the answer is a WHOLE
    rejection (Modül 11 §5.3), never a trim."""
    exposure_arg = (
        None if max_total_exposure_notional is None else max_total_exposure_notional - committed
    )
    decision = ledger.resolve_capacity(
        item_id=intent.item_id,
        snapshot=snapshot,
        requested_units=intent.desired_size,
        price=_price_of(intent),
        max_position_notional=max_position_notional,
        max_total_exposure_notional=exposure_arg,
    )
    if decision.outcome == "rejected":
        return decision, False
    headroom = ledger.available_capital - committed
    if decision.granted_notional > headroom:
        contended = CapacityDecision(
            item_id=decision.item_id,
            outcome="rejected",
            requested_units=decision.requested_units,
            granted_units=_ZERO,
            requested_notional=decision.requested_notional,
            granted_notional=_ZERO,
            binding_constraint=SOLVENCY_CONSTRAINT,
            reason=LEDGER_INSOLVENT,
            limits={**decision.limits, SOLVENCY_CONSTRAINT: max(_ZERO, headroom)},
        )
        return contended, True
    return decision, False


# -------------------------------------------------------------------------- the entry point


def arbitrate(
    *,
    ledger: PortfolioLedger,
    snapshot: PortfolioSnapshot,
    intents: Sequence[ItemIntent],
    profiles: Mapping[str, ItemArbitrationProfile],
    policy: str | None = None,
    max_position_notional: Mapping[str, Decimal] | None = None,
    max_total_exposure_notional: Decimal | None = None,
) -> ArbitrationReport:
    """Resolve P5 conflict and P6b capacity for one whole tick (ADR §8.2, §9).

    Pure with respect to the ledger: it reads ``positions``, ``available_capital`` and
    ``gross_exposure`` and writes nothing. The ledger must be FROZEN — every decision is made
    against the one published ``E(t)``, and the frozen window is what guarantees no sibling
    moved it half-way through.

    Exactly one decision is returned per intent, in pinned ``(pin_ordinal, item_id)`` order,
    and nothing is dropped: an intent that asked for no order is recorded ``not_actionable``
    with its own reason (ADR §6 rule 5), a conflict is recorded ``blocked`` with its
    counterparty, and a capacity refusal is recorded ``rejected`` with the layer that bound.

    ``max_position_notional`` is the per-item Strategy-Details limit (Modül 11 §6.1 layer 3).
    Its authority is the item's own configuration, so it is passed through to the ledger as
    given and never inferred — allocation caps a size, it never relaxes an item risk limit.

    ``max_total_exposure_notional`` is the composition-wide cap in money. It is reduced by
    this tick's running admissions before each item is asked, because the frozen ledger's
    ``gross_exposure`` cannot yet see them.

    **Two passes, and the split is the phase order, not an optimisation.** P5 runs GLOBALLY
    over the intents first (ADR §8.2 scopes it *global*, P6a/P6b *per item*), so a conflict is
    decided on what the items INTEND — which is what A-2's *"Allocation bu conflict kararindan
    sonra uygulanir"* means. Deciding it on what they turned out to afford would put allocation
    before conflict and invert the adjudication. The visible consequence, stated rather than
    hidden: an intent that P5 admits and P6b then rejects for capacity has still blocked its
    opposing sibling at P5. Both are traced, so the pair reads as what it is."""
    rule = resolve_policy(policy)
    pairs = _validate(ledger=ledger, snapshot=snapshot, intents=intents, profiles=profiles)
    limits_by_item = max_position_notional or {}
    conflicts_apply = rule.opposite_same_instrument == "blocked"

    outcomes: dict[str, ArbitrationDecision] = {}
    survivors: list[tuple[ItemArbitrationProfile, ItemIntent]] = []

    # ---- P5: cross-item conflict, global, decided on intents only ---------------------- #
    for profile, intent in pairs:
        base = _decision_base(profile, intent)
        if not intent.is_actionable:
            outcomes[intent.item_id] = ArbitrationDecision(
                **base,
                outcome="not_actionable",
                granted_units=_ZERO,
                granted_notional=_ZERO,
                reason=intent.reason,
                binding_constraint=None,
                diagnostics={"policy": rule.policy, "phase": intent.phase},
            )
            continue
        conflict = (
            _conflict_against(
                profile=profile,
                intent=intent,
                ledger=ledger,
                profiles=profiles,
                earlier=survivors,
            )
            if conflicts_apply
            else None
        )
        if conflict is None:
            survivors.append((profile, intent))
            continue
        counterparty, source, unknown_identity = conflict
        diagnostics: dict[str, Any] = {
            "policy": rule.policy,
            "conflict_source": source,
            "resolved_by": (
                "held_position_precedence" if source == "held_position" else "pin_order_tie_break"
            ),
            "share_transferred": False,
        }
        if unknown_identity:
            diagnostics["gate"] = CONFLICT_SYMBOL_UNKNOWN_GATE
        outcomes[intent.item_id] = ArbitrationDecision(
            **base,
            outcome="blocked",
            granted_units=_ZERO,
            granted_notional=_ZERO,
            reason=PORTFOLIO_CONFLICT_BLOCKED,
            binding_constraint=None,
            counterparty_item_id=counterparty,
            conflict_source=source,
            diagnostics=diagnostics,
        )

    # ---- P6b: capacity, per item, in pinned order, net of this tick's admissions ------- #
    committed = _ZERO
    for profile, intent in survivors:
        capacity, contended = _decide_capacity(
            ledger=ledger,
            snapshot=snapshot,
            intent=intent,
            committed=committed,
            max_position_notional=limits_by_item.get(intent.item_id),
            max_total_exposure_notional=max_total_exposure_notional,
        )
        committed_before = committed
        if capacity.is_admitted:
            committed += capacity.granted_notional
        outcomes[intent.item_id] = ArbitrationDecision(
            **_decision_base(profile, intent),
            outcome=capacity.outcome,
            granted_units=capacity.granted_units,
            granted_notional=capacity.granted_notional,
            reason=capacity.reason,
            binding_constraint=capacity.binding_constraint,
            limits=capacity.limits,
            diagnostics={
                "policy": rule.policy,
                "tick_committed_before": committed_before,
                "contended": contended,
                "selection_policy": CONTENTION_SELECTION_POLICY,
                "share_transferred": False,
            },
        )

    return ArbitrationReport(
        t_ms=snapshot.t_ms,
        policy=rule.policy,
        snapshot_identity=snapshot.identity,
        # Re-ordered back to the pinned order: P6b ran over the survivors, so emitting in
        # completion order would put the blocked items last and make the report's shape
        # depend on how the tick resolved instead of on the manifest.
        decisions=tuple(outcomes[intent.item_id] for _, intent in pairs),
        committed_notional=committed,
    )


def profiles_from_pins(
    pins: Sequence[tuple[str, str | None]],
) -> Mapping[str, ItemArbitrationProfile]:
    """Build the profile map from the manifest's pinned item order.

    ``pins`` is ``(item_id, instrument_id)`` in ``manifest._pinned_items`` order, so the
    ordinal is the INDEX and can never be supplied — and therefore never disagree with the
    pin. A plan re-ordered after the run changes nothing about a historical report."""
    return MappingProxyType(
        {
            item_id: ItemArbitrationProfile(
                item_id=item_id, pin_ordinal=ordinal, instrument_id=instrument_id
            )
            for ordinal, (item_id, instrument_id) in enumerate(pins)
        }
    )


__all__ = [
    "ARBITRATION_POLICY_VERSION",
    "ARBITRATION_REASONS",
    "CONFLICT_POLICY_TABLE",
    "CONFLICT_SYMBOL_UNKNOWN_GATE",
    "CONTENTION_SELECTION_NOTE",
    "CONTENTION_SELECTION_POLICY",
    "CONTENTION_SELECTION_STATUS",
    "EXPOSURE_CONSTRAINT",
    "MAX_POSITION_CONSTRAINT",
    "NET_MESSAGE",
    "NET_REMEDIATION",
    "NET_SUPPORT_STATUS",
    "NET_TRACKING_ISSUE",
    "NET_UNDEFINED_SEMANTICS",
    "PORTFOLIO_CONFLICT_BLOCKED",
    "SLEEVE_CONSTRAINT",
    "SOLVENCY_CONSTRAINT",
    "ArbitrationDecision",
    "ArbitrationError",
    "ArbitrationReport",
    "ConflictOutcome",
    "ConflictPolicyRule",
    "ConflictSource",
    "DuplicateIntentError",
    "ItemArbitrationProfile",
    "LedgerNotFrozenError",
    "MandatoryIntentNotArbitrableError",
    "MismatchedTickError",
    "UnknownArbitrationItemError",
    "UnsupportedConflictPolicyError",
    "arbitrate",
    "profiles_from_pins",
    "resolve_policy",
]
