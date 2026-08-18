"""C2 (E4b) — the two new Protocol members, P10, and the generator form.

ADR `0002` §13.2 signed G9 (`settle` + `finalize` + P10 + `iter_portfolio`) and G13 (the
end-of-data equity point **folds**, it does not append). These pin the parts of that contract
that a shipped number cannot: nothing calls ``run_portfolio`` in production yet, so the
portfolio oracles would stay green whether or not P10 booked anything at all.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from entropia.domain.backtest.execution.arbitration import ArbitrationDecision
from entropia.domain.backtest.execution.clock import ItemTickView
from entropia.domain.backtest.execution.intents import ClosingSize, ItemDecision
from entropia.domain.backtest.portfolio_engine import (
    PHASE_ORDER,
    MandatoryExit,
    PortfolioRun,
    iter_portfolio,
    run_portfolio,
)

from .portfolio_harness import ScriptedItem, _ScriptedParticipant, simulate

_ZERO = Decimal("0")


def test_phase_order_publishes_p10_as_the_last_phase() -> None:
    """The constant exists so the contract is assertable without re-reading the source.

    It had no assertion at all before this slice — the docstring's promise was unkept. P10 is
    appended, not inserted: it runs after the tick loop, so any other position would describe a
    loop this engine does not execute."""
    assert PHASE_ORDER == ("P1", "P3", "PV", "P4", "P5", "P6b", "P7", "P9", "P10")
    assert PHASE_ORDER[-1] == "P10"


class _ClosingParticipant:
    """A scripted item that ALSO forces a close at end of data, and records its ``settle``.

    Composition rather than subclassing: ``_ScriptedParticipant`` is a slotted dataclass, so a
    subclass cannot carry the two extra fields this needs. Every hook the fixture already
    answers is delegated verbatim; only ``settle`` and ``finalize`` differ.

    ``_ScriptedParticipant.finalize`` returns ``None`` — that is what keeps every existing
    oracle byte-identical. This is the opposite case, which is the one P10 exists for."""

    def __init__(self, inner: _ScriptedParticipant, *, final_pnl: str) -> None:
        self._inner = inner
        self.final_pnl = Decimal(final_pnl)
        self.settled: list[ArbitrationDecision] = []

    @property
    def identity(self):  # type: ignore[no-untyped-def]
        return self._inner.identity

    @property
    def stream(self):  # type: ignore[no-untyped-def]
        return self._inner.stream

    @property
    def instrument_id(self) -> str | None:
        return self._inner.instrument_id

    def carry(self, view: ItemTickView):  # type: ignore[no-untyped-def]
        return self._inner.carry(view)

    def mandatory_exit(self, view: ItemTickView, *, held):  # type: ignore[no-untyped-def]
        return self._inner.mandatory_exit(view, held=held)

    def entry(self, view: ItemTickView, snapshot, *, held):  # type: ignore[no-untyped-def]
        return self._inner.entry(view, snapshot, held=held)

    def settle(self, view: ItemTickView, *, admitted: ArbitrationDecision) -> None:
        self.settled.append(admitted)

    def finalize(self, view: ItemTickView) -> MandatoryExit | None:
        return MandatoryExit(
            decision=ItemDecision(kind="exit", direction="long", reason="end_of_data"),
            sizing=ClosingSize(units=Decimal("1")),
            gross_pnl=self.final_pnl,
            commission=_ZERO,
        )


def _one_item_run(final_pnl: str, *, funding_on_last: str = "0") -> tuple[PortfolioRun, object]:
    """One item that opens early and is still holding when the data ends."""
    item = ScriptedItem(
        item_id="alpha",
        share="1",
        bars=[("2024-01-01T00:00:00Z", "100"), ("2024-01-02T00:00:00Z", "110")],
        entries={"2024-01-01T00:00:00Z": ("long", "1")},
        funding={"2024-01-02T00:00:00Z": funding_on_last},
    )
    participant = _ClosingParticipant(
        _ScriptedParticipant(item=item, identity=item.identity(0), stream=item.stream(0)),
        final_pnl=final_pnl,
    )
    run = run_portfolio(
        [participant],  # type: ignore[list-item]
        pool_initial=Decimal("10000"),
        shares={"alpha": Decimal("1")},
    )
    return run, participant


def test_p10_closes_the_open_position_and_books_what_it_realized() -> None:
    """Without P10 a run ends holding open risk and the final equity is wrong, not partial."""
    run, _ = _one_item_run("250")

    assert run.final_closes, "P10 booked nothing while a position was still open"
    booked = run.final_closes[0]
    assert booked.item_id == "alpha"
    assert booked.gross_pnl == Decimal("250")
    # The ledger's own quantized figure, never a recomputed gross - commission.
    assert booked.net_pnl == Decimal("250.00")
    assert run.ledger.positions.get("alpha") is None, "the position survived end of data"


def test_the_end_of_data_point_folds_and_never_lands_twice_on_one_instant() -> None:
    """G13, the whole of it (ADR §13.2).

    The last tick moves equity (funding) and so commits a point at that ``t_ms``; P10 then
    realizes PnL at the SAME instant. Appending there — which is what a second ``commit_tick``
    does — would put two points on one ``t_ms`` and break A5's by-construction claim."""
    run, _ = _one_item_run("250", funding_on_last="5")

    instants = run.instants
    assert instants == tuple(sorted(instants)), "the curve stopped being time-ordered"
    assert len(instants) == len(set(instants)), f"two equity points share an instant: {instants}"

    # ... and the surviving point carries the SETTLED book, not the pre-close figure.
    assert run.dated_points[-1].equity == run.ledger.equity


def test_the_fold_is_not_vacuous_the_last_tick_really_did_commit_a_point() -> None:
    """Guards the test above: if the last tick committed nothing there is nothing to fold into
    and the assertion would pass for the wrong reason."""
    run, _ = _one_item_run("250", funding_on_last="5")
    last_t_ms = run.ticks[-1].t_ms

    assert run.ticks[-1].equity_point is not None, "the last tick moved no equity"
    assert run.ticks[-1].equity_point.t_ms == last_t_ms
    assert [p for p in run.dated_points if p.t_ms == last_t_ms], "nothing at the folded instant"


def test_settle_receives_the_granted_figures_not_the_requested_ones() -> None:
    """ADR §6 clause 6 — the item is told what the POOL admitted.

    An item that booked its own ``desired_size`` would be re-deciding what arbitration already
    decided, which is the silent-degradation shape C6 names."""
    _, participant = _one_item_run("0")

    assert participant.settled, "settle was never called for an admitted entry"  # type: ignore[attr-defined]
    admitted = participant.settled[0]  # type: ignore[attr-defined]
    assert admitted.item_id == "alpha"
    assert admitted.is_admitted
    assert admitted.granted_units > _ZERO


def test_run_portfolio_is_iter_portfolio_exhausted() -> None:
    """The wrapper must be the SAME run, or every oracle is measuring a different engine."""
    item = ScriptedItem(
        item_id="alpha",
        share="1",
        bars=[("2024-01-01T00:00:00Z", "100"), ("2024-01-02T00:00:00Z", "110")],
        entries={"2024-01-01T00:00:00Z": ("long", "1")},
    )
    kwargs = {"pool_initial": Decimal("10000"), "shares": {"alpha": Decimal("1")}}

    def _participant() -> _ScriptedParticipant:
        return _ScriptedParticipant(item=item, identity=item.identity(0), stream=item.stream(0))

    wrapped = run_portfolio([_participant()], **kwargs)  # type: ignore[arg-type]

    generator = iter_portfolio([_participant()], **kwargs)  # type: ignore[arg-type]
    yielded = []
    while True:
        try:
            yielded.append(next(generator))
        except StopIteration as exhausted:
            driven: PortfolioRun = exhausted.value
            break

    assert len(yielded) == len(wrapped.ticks), "the generator yielded a different tick count"
    assert driven.instants == wrapped.instants
    assert driven.ledger.equity == wrapped.ledger.equity


def test_a_participant_missing_settle_is_a_type_error_not_a_silent_flat_run() -> None:
    """The C2 stop condition, asserted at runtime as well as by mypy.

    ``hasattr`` probing would be fail-open: a participant that forgot ``settle`` would run
    flat and no gate would notice. The Protocol makes it a hard failure instead."""

    class _Forgetful:
        pass

    assert not hasattr(_Forgetful(), "settle")
    with pytest.raises((TypeError, AttributeError)):
        run_portfolio(
            [_Forgetful()],  # type: ignore[list-item]
            pool_initial=Decimal("10000"),
            shares={"alpha": Decimal("1")},
        )


def test_the_scripted_oracles_book_nothing_at_p10() -> None:
    """Why every existing portfolio oracle is byte-identical across this slice."""
    run = simulate(
        [
            ScriptedItem(
                item_id="alpha",
                share="1",
                bars=[("2024-01-01T00:00:00Z", "100")],
            )
        ]
    )
    assert run.final_closes == ()
