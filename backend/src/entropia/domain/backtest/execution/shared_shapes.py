"""The resolved-Strategy shapes a SHARED-clock run cannot drive (P2 and P8).

One table, two readers, on purpose. The phase loop refuses these shapes at
construction (``domain.backtest.participant._unsupported_shapes``, fail-LATE — the run
has already started); `C6` refuses them at ADMISSION, before a run row exists
(fail-CLOSED). Those are the same facts stated at two different moments, and the whole
value of the early refusal disappears if the two lists drift, so the predicates live
here and both readers import them.

Only the rows knowable from a :class:`StrategyConfig` ALONE are here. The engine's
table also carries rows that need a resolved ``_RunConfig`` (is an ``AllocationExecution``
attached, did an indicator plan resolve, is a capability gate down); those stay where the
resolution happens, because admission cannot ask them.

Scope: exactly the two signed gates
-----------------------------------
``G11`` (P2 — deferred / resting fills) and ``G12`` (P8 — same-direction scaling) are
signed; the admission surface emits blockers for :class:`SharedShapeKind` and nothing
else. The engine's table refuses MORE than this — partial closes, same-direction
stacking, ``close_existing`` hedges — and those refusals are deliberately NOT mirrored
into a user-visible blocker here, because no signature covers them. A shape refused by
the loop but not by admission is a run that fails late rather than never starting; that
is the pre-`C6` status quo for those rows, not a regression this module introduces.
Adding one is a one-row change plus a signature, and
``test_shared_shapes.py`` pins the current split so the omission stays visible.

* ``G11`` — ``docs/decisions/closure_g11_deferred_fill_admission_2026-08-18.md`` §Karar,
  disposition (a): entry AND exit, deferring timing AND resting order type.
* ``G12`` — ``docs/decisions/closure_product_decisions_2026-08-13.md`` §Karar 6,
  option A.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from entropia.domain.backtest.execution.fills import _fill_schedule

if TYPE_CHECKING:
    from entropia.domain.strategy.config import StrategyConfig

#: Order types that fill at the timing-chosen price. Everything else RESTS a working
#: order which only ``_phase_open_fills`` can resolve — a phase the shared path never
#: runs. Stated as the POSITIVE set so a newly added order type fails CLOSED.
IMMEDIATE_ORDER_TYPES = frozenset({"market_order", "simulation_only"})

#: ``_fill_schedule``'s answer for a fill that happens on the deciding bar itself.
#: Anything else defers or rests it into a later phase.
_IMMEDIATE_SCHEDULE = "immediate"


class SharedShapeKind(StrEnum):
    """Which SIGNED gate a violation belongs to.

    The value is a stable token, not a user-facing string: the readiness code, message
    and remediation for each kind live in ``domain/allocation/shared_mode_admission.py``
    with the rest of the shared-mode refusal texts.
    """

    #: G11 / P2 — the fill is resolved by ``_phase_open_fills`` or ``_phase_tail`` (3d),
    #: phases the shared path never runs.
    DEFERRED_FILL = "deferred_fill"
    #: G12 / P8 — the layer ladder books inside ``_phase_tail``, outside arbitration.
    SCALING = "scaling"


@dataclass(frozen=True, slots=True)
class SharedShapeViolation:
    """One violated row.

    ``detail`` is the ENGINE's sentence — the one ``UnsupportedStrategyShapeError``
    joins — and it names the phase that would have had to run and what it would have
    booked unarbitrated. Admission does not reuse it verbatim in the user-facing
    message (a Ready Check reader is not reading phase names), but it is carried so the
    two surfaces cannot describe different violations of the same row.
    """

    kind: SharedShapeKind
    field_path: str
    detail: str


def unsupported_shared_shapes(config: StrategyConfig) -> tuple[SharedShapeViolation, ...]:
    """Every signed shared-clock violation this resolved config carries, in field order.

    Empty means the config clears BOTH signed gates — it says nothing about the rows the
    engine's table owns on its own (see the module docstring).
    """
    execution = config.data.execution
    scaling = config.scaling_logic
    violations: list[SharedShapeViolation] = []
    if _fill_schedule(str(execution.entry_timing)) != _IMMEDIATE_SCHEDULE:
        violations.append(
            SharedShapeViolation(
                SharedShapeKind.DEFERRED_FILL,
                "data.execution.entry_timing",
                f"entry_timing '{execution.entry_timing}' defers or rests the entry fill; it "
                "is resolved by _phase_open_fills / _phase_tail, so the pool would arbitrate "
                "an entry the item never opens at this tick (P-C2 §C.3.7 option (a))",
            )
        )
    if _fill_schedule(str(execution.exit_timing)) != _IMMEDIATE_SCHEDULE:
        violations.append(
            SharedShapeViolation(
                SharedShapeKind.DEFERRED_FILL,
                "data.execution.exit_timing",
                f"exit_timing '{execution.exit_timing}' defers or rests the exit fill; the "
                "pool would keep holding a position the item has already decided to close",
            )
        )
    if config.data.order_config.type not in IMMEDIATE_ORDER_TYPES:
        violations.append(
            SharedShapeViolation(
                SharedShapeKind.DEFERRED_FILL,
                "data.order_config.type",
                f"order type '{config.data.order_config.type}' rests a working order that "
                "only _phase_open_fills can fill",
            )
        )
    if scaling is not None and scaling.enabled:
        violations.append(
            SharedShapeViolation(
                SharedShapeKind.SCALING,
                "scaling_logic.enabled",
                "same-direction scaling runs the layer ladder inside _phase_tail and books "
                "layers with no PortfolioSnapshot behind them; the loop refuses an admitted "
                "scale_in for the same reason (P-C2 §C.3.8 option (a))",
            )
        )
    return tuple(violations)


__all__ = [
    "IMMEDIATE_ORDER_TYPES",
    "SharedShapeKind",
    "SharedShapeViolation",
    "unsupported_shared_shapes",
]
