"""Position sizing, leverage and sleeve/exposure capacity (K-09 slice c).

Extracted VERBATIM from ``domain.backtest.engine``. Every function here is a pure
function of ``(config, price, equity)`` — none of them reads or mutates the bar
loop's state — which is why the sizing ladder (raw method -> leverage -> signal
strength -> configured min/max caps -> sleeve capacity) is now testable without
replaying a bar.

The fail-closed contract is the load-bearing part and is unchanged: an unmodelled
sizing method, an unmodelled leverage mode, a bust account or a non-positive entry
price all resolve to size ``0`` (open nothing) rather than to a fabricated notional.
``sizing_is_modelled`` / ``leverage_is_modelled`` remain the SINGLE shared source of
truth with the Ready Check blockers, so the admission gate and the engine's own
fail-closed gate can never drift apart.

Imports point DOWNWARD only (``execution.constants``), never back at ``engine`` —
``engine`` calls into this module from inside ``run_engine``, so importing ``engine``
here would form a cycle.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from entropia.domain.backtest.execution.constants import _HUNDRED, _ONE, _QTY, _ZERO
from entropia.domain.backtest.execution.costs import _effective_fill
from entropia.domain.backtest.execution.state import _Ledger, _RunConfig

if TYPE_CHECKING:
    from entropia.domain.strategy.config import (
        PositionSizeLimits,
        PositionSizing,
        StrategyConfig,
    )


def _decimal_param(params: dict[str, Any], key: str) -> Decimal | None:
    """Best-effort ``Decimal`` from a free-form ``formula_params`` entry.

    Returns ``None`` when the key is absent, the value cannot be parsed as a number,
    or it parses to a NON-FINITE ``Decimal`` (``NaN`` / ``Infinity``). ``str()`` first
    so a non-numeric value fails closed rather than a ``Decimal`` coercion surprise;
    the finiteness guard is load-bearing because ``formula_params`` is an unvalidated
    ``dict[str, Any]`` — a user-supplied ``"nan"`` constructs a quiet ``Decimal('NaN')``
    without error but then RAISES ``InvalidOperation`` on the ordered comparisons in
    the caller (crashing the run), and an ``"Infinity"`` payoff would otherwise be
    silently honoured as a real edge. Both must fail closed to notional + the L4
    warning instead."""
    if key not in params:
        return None
    try:
        value = Decimal(str(params[key]))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return value if value.is_finite() else None


def _kelly_capital_fraction(sizing: PositionSizing) -> Decimal | None:
    """Fractional-Kelly capital fraction for a ``kelly_criterion`` formula config.

    Grounded, deterministic and path-INDEPENDENT: the win probability ``W``, the
    payoff ratio ``R`` (average win / average loss) and the optional fractional-Kelly
    multiplier all come from the strategy's own ``formula_params`` — user-supplied
    edge estimates, NOT statistics estimated from the running backtest's realized
    trades. That adaptive form is deliberately DEFERRED: estimating ``W`` / ``R`` from
    outcomes-so-far is path-dependent and look-ahead-prone, so it is not modelled here
    (the honest boundary, symmetric with ``risk_based`` reading fixed config
    constants). Kelly capital fraction::

        f* = kelly_fraction * (W - (1 - W) / R)

    clamped at the LOWER bound to 0 — a non-positive edge yields 0 (do not trade),
    never a negative (bet-against-the-edge) size. No upper clamp is needed: since
    ``(1 - W) / R >= 0`` and ``W < 1``, the edge is always ``< 1`` and so is ``f*``.
    An absent ``kelly_fraction`` defaults to full Kelly (``1``); a present but
    unparseable / non-finite / out-of-range one fails closed. Returns ``None`` when
    the config is not a modelled ``kelly_criterion`` request (``custom_formula``, or a
    missing / non-finite / out-of-range ``W`` / ``R`` / explicit ``kelly_fraction``),
    so the caller falls back to notional sizing and surfaces the L4 diagnostics
    warning."""
    formula = sizing.formula_based
    if sizing.method != "formula_based_sizing" or formula is None:
        return None
    if formula.formula_type != "kelly_criterion":
        return None  # custom_formula: no safe arbitrary-expression evaluation
    win = _decimal_param(formula.formula_params, "win_probability")
    payoff = _decimal_param(formula.formula_params, "payoff_ratio")
    if win is None or payoff is None or not (_ZERO < win < _ONE) or payoff <= _ZERO:
        return None
    if "kelly_fraction" not in formula.formula_params:
        fraction = _ONE  # ABSENT → full Kelly (the documented default)
    else:
        # PRESENT: must be a valid finite multiplier in (0, 1]. An unparseable /
        # non-finite / out-of-range value fails closed to notional — never silently
        # upgraded to the most aggressive (full-Kelly) sizing.
        parsed = _decimal_param(formula.formula_params, "kelly_fraction")
        if parsed is None or not (_ZERO < parsed <= _ONE):
            return None
        fraction = parsed
    edge = win - (_ONE - win) / payoff
    return max(fraction * edge, _ZERO)


def _sizing_is_honored(config: StrategyConfig) -> bool:
    """Whether the requested sizing method is modelled by this engine version.

    ``base_position_size`` (explicit size), ``risk_based_sizing`` (a fixed % of equity
    risked across the stop distance) and ``formula_based_sizing`` with a valid
    ``kelly_criterion`` config are honored. A ``formula_based_sizing`` request that is
    ``custom_formula`` or carries missing / out-of-range Kelly params — and a
    ``risk_based_sizing`` request that carries no ``risk_based`` sub-config — are not
    modelled and FAIL CLOSED: the engine opens no position for them (F-09), surfaced
    as a diagnostics warning, never hidden — L4."""
    sizing = config.position_sizing
    if sizing.method == "base_position_size" and sizing.base_position_size is not None:
        return True
    if sizing.method == "risk_based_sizing" and sizing.risk_based is not None:
        return True
    return _kelly_capital_fraction(sizing) is not None


def sizing_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's position sizing modelled by the engine?

    The single shared source of truth for "modelled sizing", imported by the readiness
    validator so Ready Check's ``STRATEGY_SIZING_UNSUPPORTED`` blocker and the engine's
    fail-closed ``_open`` gate agree on exactly one definition — an unsupported method
    is blocked at Ready Check AND opens no position if a stale readiness state slips
    through to the worker (F-09)."""
    return _sizing_is_honored(config)


# §10.2 Exposure & leverage (post-V1 (f), Master Ref §10.2). 'No Leverage' normalizes to
# 1x regardless of the saved ``leverage`` value (spec: "No Leverage modunda 1x olarak
# normalize edilir"). 'Isolated' applies the saved positive multiplier directly to this
# position's computed size — the single-position bar-replay engine already isolates each
# position's risk to itself (nothing else is open concurrently to share margin with),
# which is exactly what isolated-margin semantics require. 'Cross' shares margin/risk
# across concurrently open positions via a portfolio-level risk model the engine does not
# implement (Master Ref §10.2: cross-margin logic depends on the Equity Allocation /
# portfolio risk model) — NOT modelled, fails closed rather than silently degrading to
# isolated semantics.
def leverage_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's leverage configuration modelled (F-07f)?

    The single shared source of truth for the readiness ``STRATEGY_LEVERAGE_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. 'No Leverage' is always modelled
    (normalizes to 1x); 'Isolated' is modelled when the saved ``leverage`` multiplier is
    a positive value (schema-enforced ``gt=0``, re-checked here defensively); 'Cross' is
    never modelled — blocked at Ready Check AND opens no position if a stale readiness
    state slips through to the worker (never a silently un-leveraged or mis-leveraged
    run)."""
    sizing = config.position_sizing
    if sizing.leverage_mode == "no_leverage":
        return True
    if sizing.leverage_mode == "cross":
        return False
    return sizing.leverage > _ZERO


def _leverage_multiplier(config: StrategyConfig) -> Decimal:
    """The resolved leverage multiplier (only called once ``leverage_is_modelled`` has
    gated position opening, so every branch here is safe/defined)."""
    sizing = config.position_sizing
    if sizing.leverage_mode == "no_leverage":
        return _ONE
    return Decimal(sizing.leverage)


def _percent_of_capital(percent: Decimal, equity: Decimal, entry_price: Decimal) -> Decimal | None:
    """``percent`` of resolved capital, expressed as a SIZE at ``entry_price``.

    The one conversion #550 turns on, in one place so the base size and the two bounds
    cannot drift: notional = capital * pct / 100, size = notional / price. ``None`` when
    the conversion is undefined (non-positive price), which callers treat as "no bound"
    rather than as zero — a bound nobody can evaluate must not silently cap to nothing.

    Quantized to the engine's ``_QTY`` step HERE rather than at each call site. The
    division is exact only by accident (1 000 / 102 is not), and a bound left at the
    28-digit context precision would put an un-representable quantity on the wire the
    moment a cap binds — the pre-#550 bounds were unit counts and needed no step."""
    if entry_price <= _ZERO:
        return None
    return (max(equity, _ZERO) * percent / _HUNDRED / entry_price).quantize(_QTY)


def _clamp_to_limits(
    size: Decimal,
    limits: PositionSizeLimits | None,
    *,
    equity: Decimal,
    entry_price: Decimal,
) -> Decimal:
    """Clamp a computed size to the strategy's configured min/max position caps (§6).

    **The caps are PERCENTAGES of resolved capital (GH #550, option A adopted
    2026-08-04).** They used to be applied verbatim as unit counts while the shipped UI
    labelled all three sizing fields ``%``; canon is unanimous the other way — Master Ref
    §10.1, doc 02's ⓘ panel (a 25% Max Single Position means a position may not exceed 25%
    of equity), the V18 mockup and the running form. Each bound is
    converted through :func:`_percent_of_capital` at this entry price, so a 25% cap means
    a notional cap of 25% of equity whatever the instrument costs.

    **Applied AFTER leverage, deliberately.** ``_position_size`` multiplies by the
    leverage and strength multipliers first, so a 25% cap bounds the notional actually
    controlled rather than the pre-leverage figure — which is what doc 02's wording asks
    for. That ordering is unchanged from before this fix.

    A no-op when no ``position_size_limits`` are configured OR the size is already
    non-positive: ``0`` is the fail-closed "do not open" sentinel returned by
    ``_raw_position_size`` (bust equity / non-positive entry price), and a ``min`` cap
    must NOT resurrect it into a live position, nor may a stray negative be lifted
    positive. A misconfigured window (``min > max`` — no size can satisfy both) fails
    closed to ``0`` rather than silently honouring one bound and violating the other;
    the comparison is done in PERCENT, before conversion, so it does not depend on a
    price being available. Only a genuinely positive size is pulled DOWN to ``max`` then
    UP to ``min``; the final ``max(., 0)`` also neutralises a nonsensical negative cap."""
    if limits is None or size <= _ZERO:
        return size
    minimum = limits.min_position_size
    maximum = limits.max_position_size
    if minimum is not None and maximum is not None and minimum > maximum:
        return _ZERO
    if maximum is not None:
        cap = _percent_of_capital(maximum, equity, entry_price)
        if cap is not None and size > cap:
            size = cap
    if minimum is not None:
        floor = _percent_of_capital(minimum, equity, entry_price)
        if floor is not None and size < floor:
            size = floor
    return max(size, _ZERO)


def max_position_size_cap(
    config: StrategyConfig, entry_price: Decimal, equity: Decimal
) -> Decimal | None:
    """The §6 ``max_position_size`` cap expressed as a QUANTITY at ``entry_price``.

    The public form of the conversion :func:`_clamp_to_limits` applies, for the two call
    sites that bind the same configured cap against an already-open position rather than
    against a freshly computed size: the scaling ladder's layer check and the
    same-direction stacking tranche check (both in ``engine``). GH #550 made the stored
    number a PERCENT, so those two comparisons would otherwise read it as a unit count
    while the sizing chain read it as a percentage — one config field, two meanings, and
    a ladder that binds at a different place than the entry that preceded it.

    ``None`` when no cap is configured OR the price cannot express it, which callers
    already treat as "this bound does not apply". Pass the SLEEVE as ``equity`` under
    allocation: that is the capital ``_position_size`` sized the position against."""
    limits = config.position_sizing.position_size_limits
    if limits is None or limits.max_position_size is None:
        return None
    return _percent_of_capital(limits.max_position_size, equity, entry_price)


def _raw_position_size(config: StrategyConfig, entry_price: Decimal, equity: Decimal) -> Decimal:
    """Deterministic sizing: explicit base size, risk-based, Kelly, else fail closed.

    ``base_position_size`` is a PERCENT of resolved capital (GH #550, option A adopted
    2026-08-04): ``size = equity * pct / 100 / entry_price``, so it is entry-price
    DEPENDENT exactly as Kelly is. It used to return the stored number verbatim as a unit
    count while the shipped UI labelled the field ``%`` — a user who typed 10 meaning 10%
    of capital opened 10 units, and the two readings diverge without bound with price
    (at an instrument costing 10 000 the unit reading opens 10x the account as notional).
    Canon is unanimous: Master Ref §10.1 ("a percentage of resolved capital"), doc 02's ⓘ
    panel (equity 10 000 with Position Size 10% opens a 1 000 nominal position), the V18
    mockup and the running form. ``risk_percentage_per_trade`` was already a true
    percent in this module, so this makes the three outliers agree with their neighbour
    rather than introducing a new convention. ``risk_based_sizing`` risks a
    fixed % of (non-negative) equity across the configured stop distance —
    ``size = equity * risk% / 100 / stop_loss_point`` — and is therefore independent
    of the entry price. ``formula_based_sizing`` with a valid ``kelly_criterion`` config
    allocates a fractional-Kelly slice of (non-negative) equity —
    ``size = equity * f* / entry_price`` — and is therefore entry-price DEPENDENT
    (Kelly sizes a fraction of CAPITAL; converting that to units divides by price),
    unlike risk-based. An unmodelled formula (``custom_formula`` / bad params) and any
    request missing its sub-config FAIL CLOSED to size 0 — never an all-in notional
    (F-09; surfaced as a diagnostics warning, L4). Every branch clamps to NON-NEGATIVE
    equity: a bust
    account yields size 0, never a negative size — a negative size would invert the
    PnL sign of every subsequent trade (review CRITICAL). The result is then clamped
    to the configured ``position_size_limits`` by ``_position_size``."""
    sizing = config.position_sizing
    if sizing.method == "base_position_size" and sizing.base_position_size is not None:
        base = _percent_of_capital(Decimal(sizing.base_position_size), equity, entry_price)
        # A non-positive entry price cannot be converted; fail closed to 0 like every
        # other price-dependent branch rather than falling back to the raw number, which
        # is what the pre-#550 reading would have opened.
        return _ZERO if base is None else base.quantize(_QTY)
    usable_equity = max(equity, _ZERO)
    if sizing.method == "risk_based_sizing" and sizing.risk_based is not None:
        risk = sizing.risk_based
        if risk.stop_loss_point > _ZERO:
            risk_capital = usable_equity * risk.risk_percentage_per_trade / _HUNDRED
            return (risk_capital / risk.stop_loss_point).quantize(_QTY)
        return _ZERO
    kelly = _kelly_capital_fraction(sizing)
    if kelly is not None:
        if entry_price > _ZERO:
            return (usable_equity * kelly / entry_price).quantize(_QTY)
        return _ZERO
    # F-09 (fail closed): the requested sizing method is NOT modelled by this engine
    # version (``custom_formula``, out-of-range / missing Kelly params, or a request
    # missing its sub-config). It opens NO position — the account is never "all-in'd"
    # by dividing all available equity by the entry price (the prior behaviour, which
    # could fabricate a full-notional trade for a strategy the user never validly
    # configured). Ready Check raises a ``STRATEGY_SIZING_UNSUPPORTED`` blocker so this
    # state cannot reach a real RUN; ``run_engine`` additionally refuses to open any
    # position when the sizing is unmodelled, so a stale/bypassed readiness state
    # reaching the worker still produces a financially inert run. The divergence is
    # surfaced (L4) via the ``position_sizing_method_unsupported`` diagnostics warning.
    return _ZERO


def _position_size(
    config: StrategyConfig,
    entry_price: Decimal,
    equity: Decimal,
    strength: Decimal = _ONE,
) -> Decimal:
    """Deterministic sizing (see ``_raw_position_size``), scaled by the leverage
    multiplier (§10.2, post-V1 (f) — a leveraged strategy controls MORE notional per
    unit of computed capital, so the multiplier scales the SIZE itself, which scales
    every downstream notional/exposure/PnL figure with it) and by the signal-strength
    multiplier (§10.3, F-07g — the SIGNAL bar's strength scales every signal-driven
    entry size; 1x for non-signal callers), then clamped to the configured
    ``position_size_limits`` min/max caps (§6). All three apply uniformly to EVERY
    sizing method — base, risk-based, Kelly and the notional fallback — so a global
    cap, leverage and strength are honoured regardless of which sizing path produced
    the size, and the LIMITS remain the final word (a strength-boosted size is still
    capped). Only called once ``leverage_is_modelled`` / ``signal_strength_is_modelled``
    have gated position opening, so both multipliers are always well-defined here. A 1x
    multiplier and a missing limits subtree are both no-ops, so behaviour is
    byte-identical to the pre-wiring engine."""
    size = _raw_position_size(config, entry_price, equity)
    if size > _ZERO:
        size = size * _leverage_multiplier(config) * strength
    return _clamp_to_limits(
        size,
        config.position_sizing.position_size_limits,
        equity=equity,
        entry_price=entry_price,
    )


def _cap_to_sleeve(desired: Decimal, sleeve_capital: Decimal, entry_price: Decimal) -> Decimal:
    """Clamp a desired size to the sleeve's remaining capacity (doc 13 §8.3/§8.4 step 5).

    ``allowed_size = min(desired, remaining_sleeve_capacity / entry_price)``. The engine
    holds at most one position at a time, so when it opens, the item's deployed capital
    is 0 and the FULL sleeve is available (the single-item foundation — a genuine
    multi-item co-simulation over a unified clock stays deferred). A non-positive sleeve
    or entry price yields 0 (the item is unallocated / cannot fill)."""
    if sleeve_capital <= _ZERO or entry_price <= _ZERO:
        return _ZERO
    cap_units = (sleeve_capital / entry_price).quantize(_QTY)
    return min(desired, cap_units)


def sleeve_capital(ctx: _RunConfig, current_equity: Decimal) -> Decimal:
    """The replayed item's sleeve cap Ci(t) at this valuation point (doc 13 §8.3).

    Compound: A(t) = max(0, E(t) - R0); Ci(t) = A(t) * wi / 100, where E(t) is the
    portfolio equity (which starts at P0 and accrues this item's realized PnL in the
    single-item foundation). Fixed: Ci = A0 * wi / 100 (constant)."""
    allocatable = (
        max(_ZERO, current_equity - ctx.reserve_nominal)
        if ctx.alloc_compound
        else ctx.allocatable_initial
    )
    return allocatable * ctx.item_share / _HUNDRED


def planned_size(
    ctx: _RunConfig,
    led: _Ledger,
    *,
    direction: str,
    fill_raw: Decimal,
    strength: Decimal,
    equity: Decimal | None = None,
) -> Decimal:
    """The size the sizing chain would open at ``fill_raw`` right now.

    The single source the entry path books from AND the F-07i (C) partial-fill logic
    measures print-size evidence against — one computation, no drift. Applies the
    full Strategy Details sizing/limits chain and (under allocation) the sleeve
    outer cap.

    ``equity`` is the valuation this size is measured against. It defaults to the
    replayed item's OWN ledger equity, which is what a standalone ``run_engine`` run has
    and the only thing it can have. A portfolio participant supplies the SHARED ``E(t)``
    instead (ADR-0002 §7): under one pool the sleeve is a slice of the portfolio's
    equity, not of a private ledger that no longer holds the capital. Passing ``None``
    is byte-identical to the pre-parameter behaviour."""
    sizing_equity = led.equity if equity is None else equity
    is_long = direction == "long"
    entry_eff = _effective_fill(
        fill_raw,
        is_buy=is_long,
        half_spread=ctx.fill_costs.half_spread,
        slip=ctx.fill_costs.slippage,
    )
    if ctx.alloc_on:
        sleeve = sleeve_capital(ctx, sizing_equity)
        return _cap_to_sleeve(
            _position_size(ctx.config, entry_eff, sleeve, strength), sleeve, entry_eff
        )
    return _position_size(ctx.config, entry_eff, sizing_equity, strength)


SIZE_RESOLVED_TO_ZERO = "size_resolved_to_zero"
"""The INDEPENDENT-mode refusal: the entry was wanted, the ladder above resolved it to a
non-positive number, and nothing was opened (GH #551, ``engine.py``'s ``_open()``). Under
allocation the more specific ``sleeve_zero_capacity`` wins instead — see the tail of
:func:`blocked_reason` — so the two never describe the same refusal.

An **F-10 restriction-trace** token, NOT an HTTP error: no request fails on this path, a run
completes normally having declined an entry. No ``ErrorBody`` is emitted, so **O-02's
``ErrorCategory`` deliberately does not apply**; declaring one would advertise ``retryable``
semantics for something that never reaches an HTTP response.

It is named HERE, beside the ladder that returns it, rather than beside the
``SLEEVE_ZERO_CAPACITY`` constant in ``execution/portfolio_ledger.py``. That module is a
CONTAINED phase-loop module whose production importers are an enumerated allowlist
(``test_backtest_portfolio_ledger.py``, ``test_oracle_portfolio_containment_gate.py``), and
the shipped single-item engine is deliberately not on it — importing it from ``engine.py``
to reach a string would have traded a live containment tripwire for a stylistic adjacency.
The dependency already runs the other way: that constant's own docstring records it as
borrowed *from* this ladder.

Master Ref §10.1 ``:7551`` (Base Position Size must be positive) and doc 02 ``:1014``
(*"When selected, Position Size required >0"*) require the positivity; neither names a wire
token for the runtime refusal, so the value is pinned by test rather than by canon."""


def blocked_reason(ctx: _RunConfig, led: _Ledger) -> str:
    """Why a wanted entry produced NO fill (F-10 restriction trace)."""
    if led.portfolio_block_reason is not None:
        # A portfolio-rules gate (conflict block / exposure cap) set the concrete
        # reason at decision time; consume it so a later unrelated block cannot
        # inherit a stale portfolio reason.
        reason = led.portfolio_block_reason
        led.portfolio_block_reason = None
        return reason
    if not ctx.sizing_ok:
        return "sizing_unsupported"
    if not ctx.leverage_ok:
        return "leverage_unsupported"
    if not ctx.strength_ok:
        return "signal_strength_unsupported"
    if not ctx.capability_ok:
        # F-05: checked LAST of the unsupported reasons, deliberately. Where a
        # per-domain predicate already explains the refusal (cross leverage,
        # trend-adjusted strength, ...) that reason is the more specific and
        # already-contracted trace value, so the matrix must not overwrite it. This
        # branch is what reports the options NO per-domain gate covers — the
        # historical-slippage case the matrix was added for.
        return "capability_not_in_build"
    if ctx.alloc_on:
        return "sleeve_zero_capacity"
    return "no_fill"
