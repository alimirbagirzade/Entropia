"""The unified valuation clock — merged decision-time axis (ADR 0002 §4, ADIM 15). DB-free.

What these tests are for: ADR 0002 replaces the engine's item loop with a merged timestamp
axis, and ADIM 15 builds that axis and nothing else. So they pin two different kinds of
claim, and the distinction matters when one of them fails later:

* the axis's OWN contract — union/dedup, ordering, staleness reporting, fail-closed refusal,
  streaming, determinism;
* the BOUNDARY the ADR draws around this slice — the clock is pure, nothing imports it, no
  manifest field ships, ``ENGINE_VERSION`` does not move, and every item's bar sequence comes
  back off the axis exactly as it went in, so item-local machinery (MTF resampling, the
  research available-time gate) cannot be disturbed by a sibling's bars.

The interleaving fixture is the one from ``test_shared_allocation_containment.py`` — item A
moves at 01:00/04:00, item B in between at 02:00/03:00. That test proves the shipped
sequential fold produces a curve which is not a time series; here the same four instants are
shown landing on one ordered axis, which is the thing the fold could not do.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropia.domain.backtest.engine import _epoch_ms_or_none
from entropia.domain.backtest.execution.clock import (
    CLOCK_POLICY_VERSION,
    ClockTick,
    DuplicateItemStreamError,
    ItemBarStream,
    NonMonotonicBarStreamError,
    UnplaceableBarTimestampError,
    iter_ticks,
    tick_key,
    timeline_identity,
)
from entropia.domain.backtest.execution.rules import bar_epoch_ms
from entropia.domain.backtest.funding import parse_utc
from entropia.domain.backtest.indicators import BlockEvaluator, IndicatorSpec
from entropia.domain.backtest.manifest import ENGINE_VERSION
from entropia.domain.research_data.time_policy import is_eligible_for_decision

_H = 3_600_000  # one hour in ms


def _row(timestamp: str, close: str = "100") -> dict[str, Any]:
    price = Decimal(close)
    return {
        "timestamp": timestamp,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": Decimal("1"),
    }


def _stream(
    item_id: str,
    pin_ordinal: int,
    timestamps: list[str],
    *,
    batch_size: int = 2,
    closes: list[str] | None = None,
) -> ItemBarStream:
    prices = closes if closes is not None else ["100"] * len(timestamps)
    rows = [_row(ts, price) for ts, price in zip(timestamps, prices, strict=True)]
    batches = [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]
    return ItemBarStream(item_id=item_id, pin_ordinal=pin_ordinal, batches=batches)


def _hours(*hours: int) -> list[str]:
    return [f"2024-01-01T{h:02d}:00:00Z" for h in hours]


def _axis(ticks: list[ClockTick]) -> list[int]:
    return [tick.t_ms for tick in ticks]


def _deciding(tick: ClockTick) -> list[str]:
    return [view.item_id for view in tick.deciding]


def _recovered(ticks: list[ClockTick], item_id: str) -> list[str]:
    """Every bar timestamp item ``item_id`` sees, in the order the axis hands them over."""
    out: list[str] = []
    for tick in ticks:
        view = tick.view_for(item_id)
        assert view is not None
        out.extend(bar.timestamp for bar in view.bars)
    return out


# --------------------------------------------------------------------------- #
# Axis construction                                                            #
# --------------------------------------------------------------------------- #


def test_single_item_axis_is_that_items_own_bar_axis() -> None:
    """ADR §3.2 single-item reduction: with one item the merged axis IS its bar axis.

    This is the invariant the whole programme's blast radius is bounded by — if it ever
    stops holding, a single-Strategy composition cannot stay byte-identical (A14)."""
    stamps = _hours(1, 2, 3, 4)
    ticks = list(iter_ticks([_stream("a", 0, stamps)]))

    assert _axis(ticks) == [_epoch_ms_or_none(ts) for ts in stamps]
    for tick, ts in zip(ticks, stamps, strict=True):
        assert len(tick.views) == 1
        view = tick.views[0]
        assert view.is_decision
        assert [bar.timestamp for bar in view.bars] == [ts]
        assert view.staleness_ms == 0


def test_merged_axis_is_the_sorted_union_of_both_items_decision_times() -> None:
    """The containment fixture, on one clock.

    ``test_composite_portfolio_curve_is_not_time_ordered`` shows the shipped fold emitting
    01:00, 04:00, 02:00, 03:00 — item order, not time order. The same two items produce a
    strictly ascending axis here, and each instant belongs to exactly the item that moved."""
    ticks = list(iter_ticks([_stream("a", 0, _hours(1, 4)), _stream("b", 1, _hours(2, 3))]))

    assert _axis(ticks) == [_epoch_ms_or_none(ts) for ts in _hours(1, 2, 3, 4)]
    assert _axis(ticks) == sorted(_axis(ticks))
    assert [_deciding(tick) for tick in ticks] == [["a"], ["b"], ["b"], ["a"]]
    # Every tick still carries a view for BOTH items — a silent item is visible, not absent,
    # because ADIM 17's E(t) has to account for its open position (ADR §5).
    assert all(len(tick.views) == 2 for tick in ticks)


def test_a_shared_instant_collapses_to_one_tick_with_both_items_deciding() -> None:
    """Dedup is of the axis: one instant, one valuation point, two deciding items."""
    ticks = list(iter_ticks([_stream("a", 0, _hours(1, 2)), _stream("b", 1, _hours(2, 3))]))

    assert _axis(ticks) == [_epoch_ms_or_none(ts) for ts in _hours(1, 2, 3)]
    assert _deciding(ticks[1]) == ["a", "b"]


def test_offset_forms_of_the_same_instant_collapse_to_one_tick() -> None:
    """ADR §4.1: ``t_ms``, not the raw string, is the key.

    ``"2024-01-01T02:00:00+01:00"`` sorts after ``"2024-01-01T01:00:00Z"`` as text while
    naming the same instant. A string axis would emit two valuation points here and hand the
    two items different snapshots at one moment; the epoch key emits one."""
    a = _stream("a", 0, ["2024-01-01T01:00:00Z"])
    b = _stream("b", 1, ["2024-01-01T02:00:00+01:00"])
    ticks = list(iter_ticks([a, b]))

    assert len(ticks) == 1
    assert ticks[0].t_ms == _epoch_ms_or_none("2024-01-01T01:00:00Z")
    assert _deciding(ticks[0]) == ["a", "b"]


def test_a_mixed_offset_axis_orders_by_instant_and_not_by_text() -> None:
    """The stronger form of the previous test: text order and instant order DISAGREE here.

    Item B's first bar reads ``03:00-03:00`` (= 06:00Z) and sorts BEFORE item A's ``05:00Z``
    as text while happening an hour after it. A merge keyed on the raw string emits the two
    instants in the wrong order and the axis stops being ascending — which is the single
    property every "no future data" guarantee downstream is built on."""
    a = _stream("a", 0, ["2024-01-01T05:00:00Z"])
    b = _stream("b", 1, ["2024-01-01T03:00:00-03:00", "2024-01-01T07:00:00Z"])
    assert "2024-01-01T03:00:00-03:00" < "2024-01-01T05:00:00Z"  # the trap, spelled out

    ticks = list(iter_ticks([a, b]))
    axis = _axis(ticks)

    assert axis == sorted(axis)
    assert axis == [tick_key(ts) for ts in _hours(5, 6, 7)]
    assert [_deciding(tick) for tick in ticks] == [["a"], ["b"], ["b"]]


def test_one_sided_axis_keeps_both_items_present_throughout() -> None:
    """Item A runs out before item B starts: no overlap at all, one continuous axis."""
    ticks = list(iter_ticks([_stream("a", 0, _hours(1, 2)), _stream("b", 1, _hours(5, 6))]))

    assert _axis(ticks) == [_epoch_ms_or_none(ts) for ts in _hours(1, 2, 5, 6)]
    assert [_deciding(tick) for tick in ticks] == [["a"], ["a"], ["b"], ["b"]]
    # B has not started yet at 01:00 -> nothing to carry forward, and the clock says so
    # rather than inventing a price.
    early_b = ticks[0].view_for("b")
    assert early_b is not None and early_b.last_closed is None and early_b.staleness_ms is None
    # A has stopped by 06:00 -> its last close is still nameable, and its age is measured.
    late_a = ticks[3].view_for("a")
    assert late_a is not None and late_a.last_closed is not None
    assert late_a.last_closed.timestamp == "2024-01-01T02:00:00Z"
    assert late_a.staleness_ms == 4 * _H


def test_an_empty_stream_set_and_a_barless_item_both_stay_honest() -> None:
    assert list(iter_ticks([])) == []
    # A stream with no bars contributes no instants but is still a member of every tick.
    ticks = list(iter_ticks([_stream("a", 0, _hours(1)), _stream("b", 1, [])]))
    assert len(ticks) == 1
    silent = ticks[0].view_for("b")
    assert silent is not None
    assert silent.bars == () and not silent.is_decision and silent.last_closed is None
    # An item that is not part of the run has no view at all — asked for, it is absent
    # rather than fabricated as a silent one.
    assert ticks[0].view_for("not-in-this-run") is None


def test_heterogeneous_timeframes_interleave_without_borrowing_bars() -> None:
    """A 1h item and a 15m item share an axis; neither is handed the other's bars.

    This is the property every item-local subsystem rests on. Recovering each item's bar
    sequence off the merged axis returns exactly its input sequence, in order, so anything
    computed per item from those bars — indicators, MTF resampling, the availability gate —
    sees precisely what it sees today."""
    hourly = _hours(1, 2)
    quarterly = [
        "2024-01-01T01:00:00Z",
        "2024-01-01T01:15:00Z",
        "2024-01-01T01:30:00Z",
        "2024-01-01T01:45:00Z",
        "2024-01-01T02:00:00Z",
    ]
    ticks = list(iter_ticks([_stream("h", 0, hourly), _stream("q", 1, quarterly)]))

    assert _axis(ticks) == [_epoch_ms_or_none(ts) for ts in quarterly]
    assert _recovered(ticks, "h") == hourly
    assert _recovered(ticks, "q") == quarterly
    # At 01:15 the hourly item simply does not decide — it is not fed a 15m bar.
    hourly_at_0115 = ticks[1].view_for("h")
    assert hourly_at_0115 is not None
    assert hourly_at_0115.bars == () and not hourly_at_0115.is_decision


def test_a_duplicate_instant_inside_one_item_is_surfaced_not_collapsed() -> None:
    """Two bars at one instant in one pinned stream: the AXIS advances once, the DATA stays.

    Collapsing them would need a merge rule canon does not supply, and dropping one would
    silently discard pinned market data. The engine replays both today; the clock hands both
    over and lets a later slice decide what that means."""
    a = _stream("a", 0, ["2024-01-01T01:00:00Z", "2024-01-01T01:00:00Z"], closes=["10", "20"])
    ticks = list(iter_ticks([a]))

    assert len(ticks) == 1
    view = ticks[0].views[0]
    assert [str(bar.close) for bar in view.bars] == ["10", "20"]
    # The cursor follows the LAST of them, matching the engine's forward replay.
    assert view.last_closed is not None and str(view.last_closed.close) == "20"


# --------------------------------------------------------------------------- #
# No future data, staleness reported but not resolved                          #
# --------------------------------------------------------------------------- #


def test_no_view_ever_carries_data_from_the_future() -> None:
    """Structural look-ahead proof: at tick ``t`` nothing at or beyond ``t`` has leaked in.

    Every fresh bar is stamped exactly ``t``, and the retained ``last_closed`` is at most
    ``t``. A cursor that had read ahead would show up here as a bar with ``t' > t``."""
    ticks = list(iter_ticks([_stream("a", 0, _hours(1, 3, 5)), _stream("b", 1, _hours(2, 4, 6))]))

    assert ticks
    for tick in ticks:
        for view in tick.views:
            assert all(tick_key(bar.timestamp) == tick.t_ms for bar in view.bars)
            if view.last_closed_t_ms is not None:
                assert view.last_closed_t_ms <= tick.t_ms


def test_a_sparse_item_reports_its_last_close_and_measures_staleness_only() -> None:
    """Missing/stale data: the clock reports, it does not decide (OD-2 is open).

    It says "no fresh bar", names the last closed one and how old it is. Whether that close
    may be carried forward to mark an open position, and for how long, is the unanswered
    OD-2 — so nothing here fills the gap, and no threshold exists to be tuned."""
    dense = _hours(1, 2, 3, 4)
    ticks = list(iter_ticks([_stream("dense", 0, dense), _stream("sparse", 1, _hours(1, 4))]))

    ages = [(tick.view_for("sparse").staleness_ms) for tick in ticks]  # type: ignore[union-attr]
    assert ages == [0, _H, 2 * _H, 0]
    silent = ticks[2].view_for("sparse")
    assert silent is not None
    assert not silent.is_decision
    assert silent.last_closed is not None
    assert silent.last_closed.timestamp == "2024-01-01T01:00:00Z"


# --------------------------------------------------------------------------- #
# Ordering and determinism                                                     #
# --------------------------------------------------------------------------- #


def test_views_are_ordered_by_pin_ordinal_then_item_id() -> None:
    """ADR §4.4 tie-break. ``pin_ordinal`` comes from the manifest's deterministic pin sort,
    so this order is never DOM order or API arrival order."""
    streams = [
        _stream("zeta", 1, _hours(1)),
        _stream("alpha", 1, _hours(1)),
        _stream("mid", 0, _hours(1)),
    ]
    tick = next(iter_ticks(streams))

    assert [view.item_id for view in tick.views] == ["mid", "alpha", "zeta"]
    assert [view.pin_ordinal for view in tick.views] == [0, 1, 1]


def test_the_order_streams_are_passed_in_cannot_change_the_axis() -> None:
    """doc 13 §13: no user-visible ordering may change the outcome."""

    def build() -> list[ItemBarStream]:
        return [_stream("a", 0, _hours(1, 4)), _stream("b", 1, _hours(2, 3))]

    forward = list(iter_ticks(build()))
    reversed_input = list(iter_ticks(list(reversed(build()))))

    assert _axis(forward) == _axis(reversed_input)
    assert [_deciding(t) for t in forward] == [_deciding(t) for t in reversed_input]
    assert [[v.item_id for v in t.views] for t in forward] == [
        [v.item_id for v in t.views] for t in reversed_input
    ]


def test_the_axis_is_identical_on_a_rerun() -> None:
    """Deterministic replay: no wall clock, no randomness, no set/dict iteration effect."""

    def run() -> str:
        streams = [_stream("a", 0, _hours(1, 4)), _stream("b", 1, _hours(2, 3))]
        return timeline_identity(tick.t_ms for tick in iter_ticks(streams))

    assert run() == run()


def test_batch_chunking_does_not_change_the_axis() -> None:
    """Cross-item batch invariance (ADR §11 / A18) at the clock layer: how each item's bars
    were chunked by the reader is an I/O detail and must not reach the axis."""

    def axis(batch_a: int, batch_b: int) -> list[int]:
        return _axis(
            list(
                iter_ticks(
                    [
                        _stream("a", 0, _hours(1, 3, 5), batch_size=batch_a),
                        _stream("b", 1, _hours(2, 4, 6), batch_size=batch_b),
                    ]
                )
            )
        )

    assert axis(1, 1) == axis(3, 1) == axis(1, 3) == axis(2, 3)


def test_the_axis_does_not_materialize_the_streams() -> None:
    """ADR §11: a streaming k-way merge, not a load-everything-then-sort.

    Counted at the source: producing the FIRST tick must not drain 200 rows of input."""
    pulled = {"n": 0}

    def counting(timestamps: list[str]) -> Iterator[list[dict[str, Any]]]:
        for ts in timestamps:
            pulled["n"] += 1
            yield [_row(ts)]

    streams = [
        ItemBarStream("a", 0, counting(_hours(*range(0, 20)))),
        ItemBarStream("b", 1, counting(_hours(*range(0, 20)))),
    ]
    first = next(iter_ticks(streams))

    assert first.t_ms == _epoch_ms_or_none("2024-01-01T00:00:00Z")
    # Priming one row per item plus the single read-ahead that closes the instant's group.
    assert pulled["n"] <= 4


# --------------------------------------------------------------------------- #
# Fail closed — never a degraded axis                                          #
# --------------------------------------------------------------------------- #


def test_an_unplaceable_timestamp_fails_the_axis_instead_of_being_skipped() -> None:
    """ADR §11 / Modül 12 §9: a tick that cannot be placed fails the run.

    Note the K-01 contract this inherits: a NAIVE timestamp is unresolvable, not assumed
    UTC (``parse_utc(source_zone=None)``), so it is refused here too. That is stricter than
    ``indicators._epoch_seconds``, which assumes UTC for a naive value — the divergence is
    pinned in ``test_tick_key_agrees_with_the_shipped_epoch_helpers``."""
    for bad in ("not-a-time", "2024-01-01T01:00:00"):
        with pytest.raises(UnplaceableBarTimestampError):
            list(iter_ticks([_stream("a", 0, [bad])]))


def test_a_backwards_stream_fails_the_axis() -> None:
    """A k-way merge over an unsorted input yields an axis that is not sorted, and every
    downstream no-look-ahead guarantee would be void. Refuse rather than emit it."""
    with pytest.raises(NonMonotonicBarStreamError):
        list(iter_ticks([_stream("a", 0, _hours(3, 1))]))


def test_two_streams_for_one_item_are_refused() -> None:
    with pytest.raises(DuplicateItemStreamError):
        list(iter_ticks([_stream("a", 0, _hours(1)), _stream("a", 1, _hours(2))]))


def test_an_uncoercible_row_is_dropped_exactly_as_the_engine_drops_it() -> None:
    """The clock cannot admit a bar the replay would never have seen, so it reuses the
    engine's own coercion boundary (``state._normalize``) rather than a second rule."""
    good = _row("2024-01-01T01:00:00Z")
    missing_close = {k: v for k, v in _row("2024-01-01T02:00:00Z").items() if k != "close"}
    ticks = list(iter_ticks([ItemBarStream("a", 0, [[good, missing_close]])]))

    assert _axis(ticks) == [_epoch_ms_or_none("2024-01-01T01:00:00Z")]


# --------------------------------------------------------------------------- #
# Item-local semantics the clock must not disturb                              #
# --------------------------------------------------------------------------- #


def test_the_availability_gate_is_evaluated_at_the_items_own_decision_time() -> None:
    """A sibling's tick is not this item's decision time (ADR §5).

    A research record that becomes available at 02:30 must not be readable by the hourly
    item at 02:00, and must not become readable merely because a faster sibling produced a
    tick at 02:30 — the hourly item is not deciding there. It becomes eligible at that
    item's OWN next decision, 03:00. This is the property PR #560's parity tests protect."""
    available_at = parse_utc("2024-01-01T02:30:00Z", source_zone=None)
    assert available_at is not None

    slow = _stream("slow", 0, _hours(1, 2, 3))
    fast = _stream("fast", 1, ["2024-01-01T02:30:00Z"])
    ticks = list(iter_ticks([slow, fast]))

    eligible_at: list[str] = []
    for tick in ticks:
        view = tick.view_for("slow")
        assert view is not None
        if not view.is_decision:
            continue  # not a decision for this item -> the gate is not even asked
        decision_time = parse_utc(view.bars[-1].timestamp, source_zone=None)
        assert decision_time is not None
        if is_eligible_for_decision(
            available_at=available_at,
            decision_time=decision_time,
            has_instrument_mapping=True,
        ):
            eligible_at.append(view.bars[-1].timestamp)

    assert eligible_at == ["2024-01-01T03:00:00Z"]


def test_higher_timeframe_bucketing_is_unchanged_by_a_siblings_ticks() -> None:
    """MTF stays item-local (ADR §5): the shipped one-base-bar closed-candle lag survives.

    The hourly item's bars are pulled back off an axis it shares with a 30-minute sibling and
    fed to the same evaluator ``test_backtest_multi_timeframe`` uses. The signal sequence is
    identical to feeding the item alone, and candle 4's LONG cross still appears only once
    the next bucket opens (bar 10) — never on the forming candle (bar 9)."""
    closes = ["10", "10", "10", "10", "10", "10", "10", "10", "11", "12", "12", "12"]
    hourly = _hours(*range(12))
    sibling = [f"2024-01-01T{h:02d}:30:00Z" for h in range(12)]

    def signals(bars: list[tuple[str, Decimal]]) -> list[str | None]:
        ev = BlockEvaluator(
            IndicatorSpec(
                block_id="blk_htf",
                canonical_key="ta.sma",
                length=2,
                direction="long_and_short",
                requirement="required",
                validity="until_opposite_signal",
                resample_seconds=7200,
            )
        )
        out: list[str | None] = []
        for ts, close in bars:
            ev.update(close, timestamp=ts)
            out.append(ev.current_signal)
        return out

    alone = signals([(ts, Decimal(c)) for ts, c in zip(hourly, closes, strict=True)])

    ticks = list(
        iter_ticks(
            [
                _stream("hourly", 0, hourly, closes=closes),
                _stream("sibling", 1, sibling),
            ]
        )
    )
    from_axis_bars: list[tuple[str, Decimal]] = []
    for tick in ticks:
        view = tick.view_for("hourly")
        assert view is not None
        from_axis_bars.extend((bar.timestamp, bar.close) for bar in view.bars)

    assert [ts for ts, _ in from_axis_bars] == hourly
    assert signals(from_axis_bars) == alone
    assert alone[9] is None
    assert alone[10] == "long"


def test_tick_key_agrees_with_the_shipped_epoch_helpers() -> None:
    """One epoch convention, three call sites. ``tick_key`` is a third wrapper over
    ``parse_utc`` only so the clock does not import ``execution.rules``, which ADIM 19
    retires — it must never become a second convention."""
    for ts in ("2024-01-01T01:00:00Z", "2024-01-01T02:00:00+01:00", "1970-01-01T00:00:00Z"):
        assert tick_key(ts) == _epoch_ms_or_none(ts) == bar_epoch_ms(ts)
    for bad in ("not-a-time", "", "2024-01-01T01:00:00"):
        assert tick_key(bad) is None
        assert _epoch_ms_or_none(bad) is None
        assert bar_epoch_ms(bad) is None


# --------------------------------------------------------------------------- #
# Versioning, identity, and the ADIM 15 boundary                               #
# --------------------------------------------------------------------------- #


def test_clock_policy_version_is_pinned() -> None:
    assert CLOCK_POLICY_VERSION == "clock-policy-v1"


def test_timeline_identity_is_deterministic_and_discriminating() -> None:
    """Two axes share an identity exactly when they are the same instants in the same order
    under the same policy."""
    axis = [1, 2, 3]
    assert timeline_identity(axis) == timeline_identity(iter([1, 2, 3]))
    assert timeline_identity(axis) != timeline_identity([1, 3, 2])
    assert timeline_identity(axis) != timeline_identity([1, 2, 3, 4])
    assert timeline_identity([]) != timeline_identity([0])
    assert timeline_identity(axis) != timeline_identity(axis, policy_version="clock-policy-v2")
    assert len(timeline_identity(axis)) == 64


def test_the_clock_is_not_wired_into_production_yet() -> None:
    """ADR §12: the ADIM 15 rollback is "delete the module — nothing imports it".

    That is only true while it stays true, and it is exactly what keeps every shipped digest
    still. When ADIM 18 wires ``run_portfolio`` in, this test is the one that must be updated
    deliberately — it should never fail by accident."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = [
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "clock.py" and "execution.clock" in path.read_text(encoding="utf-8")
    ]
    assert importers == []


def test_no_clock_field_ships_in_the_manifest_yet_and_the_engine_version_stands() -> None:
    """ADR §10.3 places ``clock_policy_version`` and its neighbours in ADIM 20, together with
    the ``ENGINE_VERSION`` bump. ADIM 15 changes no replay, so no namespace may shift."""
    manifest_src = (
        Path(__file__).resolve().parents[2] / "src/entropia/domain/backtest/manifest.py"
    ).read_text(encoding="utf-8")

    assert ENGINE_VERSION == "backtest-engine-v18-gap-adjusted-stop-fill"
    for field in (
        "clock_policy_version",
        "arbitration_policy_version",
        "mark_staleness_policy",
        "engine_allocation_policy_version",
    ):
        assert field not in manifest_src
