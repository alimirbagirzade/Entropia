"""Instrument registry state machine (GAP-16). Pure transition validation.

Mirrors ``domain/esp/state_machine.py``. An instrument is created ``active`` and
may be ``deprecated`` (Admin-only at the policy layer; this module validates only
legality). A deprecated instrument is terminal for new selection — historical
``instrument_id`` references keep resolving (Master §8.1).
"""

from __future__ import annotations

from entropia.domain.instrument.enums import InstrumentState
from entropia.shared.errors import ConflictError

_ALLOWED: dict[InstrumentState, frozenset[InstrumentState]] = {
    InstrumentState.ACTIVE: frozenset({InstrumentState.DEPRECATED}),
    InstrumentState.DEPRECATED: frozenset(),
}


class IllegalInstrumentTransition(ConflictError):
    code = "ILLEGAL_INSTRUMENT_TRANSITION"
    message = "That instrument registry state transition is not allowed."


def can_deprecate(current: InstrumentState) -> bool:
    """Deprecation is only legal from ``active``."""
    return current == InstrumentState.ACTIVE


def next_instrument_state(current: InstrumentState, target: InstrumentState) -> InstrumentState:
    """Validate and return the target state, or raise IllegalInstrumentTransition."""
    if target not in _ALLOWED.get(current, frozenset()):
        raise IllegalInstrumentTransition(
            f"Cannot move instrument state from '{current}' to '{target}'."
        )
    return target
