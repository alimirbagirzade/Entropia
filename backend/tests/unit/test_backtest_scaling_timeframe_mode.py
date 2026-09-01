"""S5c — Scaling Timeframe Structure + Logic-Based Scaling end to end (doc 02 §5.7).

``ScalingLogic`` carried a single flat ``timeframe`` and nothing else: the spec's three-way
Timeframe Mode and its typed Custom Timeframe Sequence did not exist, and Logic-Based
Scaling — the sequence's only consumer — was ``future_dev``. These tests pin the whole
slice:

* **schema** — ``timeframe_mode`` defaults to ``same_strategy``;
  ``custom_timeframe_sequence`` is REQUIRED, non-empty and STRICTLY INCREASING under
  ``custom_sequence``, and DROPPED under every other mode (the disabled-subtree
  convention, mirroring ``RestrictionsFilters.min_true_count``);
* **predicate** — logic-based scaling, ``custom_sequence`` and (since GH #547)
  ``increasing_by_layer`` leave the fail-closed L4 set, while an UNBOUNDED logic ladder
  deliberately stays in it;
* **engine BEHAVIOUR** — not merely that the fields parse, but that they change which bars
  fill layers: the same signal path under ``same_strategy``, under a coarse
  ``custom_sequence`` and under ``increasing_by_layer`` produces different ladders; the
  sequence length bounds one and the canonical ladder's remaining rungs bound the other
  (the signed GH #547 exhaustion decision — past 1D the ladder runs out);
* **manifest** — the ENGINE_VERSION bump shifts the ``execution_key`` namespace.

ADJUDICATION (doc 02 §5.7 table vs. §6.1 ⓘ panel). The §5.7 table lists
``scaling.timeframe_mode`` as a general scaling field, while §6.1's panel text — which §6's
CONTENT RULE makes contractual — says the sequence drives Logic-Based Scaling ONLY,
because Price-Distance Based Scaling is triggered directly by price distance and so (the
panel's words) does not use this timeframe sequence. §6.1 WINS: its reasoning is
mechanical rather than incidental (a price comparison evaluates no indicator, so it has no
candle to close on),
and the narrower reading cannot silently corrupt the already-shipped price ladder.
``test_price_distance_ladder_ignores_the_sequence`` is that adjudication as an executable
assertion. S5c therefore also landed Logic-Based Scaling itself rather than shipping a
field with no reachable behaviour.

Deliberately NO literal ``ENGINE_VERSION`` assertion (post-PR-#45 convention): the shift is
proven by comparing the live constant against a distinct prior pin, so this module does not
re-break on the next bump the way the S5a copy did.

Bars are 15m here, not the daily bars ``test_backtest_scaling.py`` uses — a per-layer
timeframe gate is invisible unless the base bar is finer than the layer's timeframe.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from entropia.domain.backtest.engine import EngineOutput, run_engine, scaling_is_modelled
from entropia.domain.backtest.execution.scaling import (
    increasing_ladder_depth,
    layer_bucket,
    layer_timeframe,
)
from entropia.domain.backtest.indicators import (
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
    timeframe_seconds,
)
from entropia.domain.backtest.manifest import ENGINE_VERSION, build_run_manifest
from entropia.domain.strategy.config import CANONICAL_TIMEFRAMES, StrategyConfig
from tests.unit.engine_signal_plan import PLAN_MA_LENGTH, sma_entry_plan

# The ENGINE_VERSION this slice replaced — the namespace the execution_key must leave.
_PRIOR_ENGINE_VERSION = "backtest-engine-v18-min-n-filtered-events-artifact"

_BASE_TF_MINUTES = 15
_START = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)

_SCALE_BLOCK = {
    "block_id": "sc_1",
    "display_order": 0,
    "package_ref": {
        "package_root_id": "pkg_1",
        "package_revision_id": "pkgrev_1",
        "package_content_hash": "pkghash_1",
    },
    "trigger_source": "indicator_native_trigger",
    "requirement": "required",
}


def _scale_plan() -> IndicatorPlan:
    """The entry plan PLUS a resolved Logic-Based Scaling block.

    The scaling block is a SHORT (3-bar) ``ta.sma`` cross, deliberately different from the
    20-bar entry MA: the two signals must be independently controllable, which is the whole
    point of scaling on its own indicator. ``current_candle_only`` keeps each cross an EDGE,
    so every up-cross is one scaling proposal rather than a permanently-true signal.
    """
    entry = sma_entry_plan(length=PLAN_MA_LENGTH)
    return IndicatorPlan(
        entry_rule=entry.entry_rule,
        entry_specs=entry.entry_specs,
        scale_specs=(
            IndicatorSpec(
                block_id="sc_1",
                canonical_key="ta.sma",
                length=3,
                direction="long",
                requirement="required",
                validity="current_candle_only",
            ),
        ),
        scale_rule=SignalRule(rule="required_indicator_blocks_only"),
    )


def _scaling(
    *,
    method: str = "logic_based_scaling",
    timeframe_mode: str = "same_strategy",
    custom_timeframe_sequence: list[str] | None = None,
    max_layers: int | None = 4,
    add_size_value: str | None = "50",
    retracement: str = "1.0",
) -> dict[str, Any]:
    """An enabled scaling subtree with an explicit timeframe structure."""
    scaling: dict[str, Any] = {
        "enabled": True,
        "timeframe": "same_as_base_tf",
        "timeframe_mode": timeframe_mode,
        "method": method,
        "add_size": "percent_of_initial",
    }
    if add_size_value is not None:
        scaling["add_size_value"] = add_size_value
    if method == "logic_based_scaling":
        scaling["logic_scaling"] = {"indicator_blocks": [_SCALE_BLOCK]}
    else:
        scaling["price_scaling"] = {"retracement_distance": retracement, "layers": 4}
    if custom_timeframe_sequence is not None:
        scaling["custom_timeframe_sequence"] = custom_timeframe_sequence
    if max_layers is not None:
        scaling["scaling_limits"] = {"max_scaling_layers": max_layers}
    return scaling


def _config(*, scaling: dict[str, Any] | None = None) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Mirrors ``test_backtest_scaling._config``: zero costs so a fill lands exactly on the
    resolved price, no protection stop so the ladder governs the position's life, and
    ``opposite_direction_hedge="ignore"`` so an adverse bar does not close the position
    before the later layers can trigger (that is the §9 hedge rule, not the scaling rule).
    """
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Scaling TF Mode Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z",
                },
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": "inherit"},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": {},
            "protection_stop_logic": {},
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "scaling_logic": scaling,
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {"opposite_direction_hedge": "ignore"},
        }
    )


def _bar(
    index: int, o: str, h: str, low: str, c: str, *, minutes: int = _BASE_TF_MINUTES
) -> dict[str, Any]:
    """One bar, ``index`` slots of ``minutes`` after 2024-01-01T00:00Z (default 15m)."""
    ts = _START + timedelta(minutes=minutes * index)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": "10",
    }


# After the entry, close OSCILLATES so the short scaling MA is crossed upward repeatedly.
# Each up-cross is one scaling proposal; the whole staircase stays well ABOVE the 20-bar
# entry MA (parked at 90) so no bar is an opposite signal that would close the position.
_OSCILLATION: list[tuple[str, str, str, str]] = [
    ("100", "100.2", "99.8", "100"),  # down off the entry close
    ("100", "103.2", "100", "103"),  # up-cross -> scaling proposal (bar 22)
    ("103", "103", "99.8", "100"),  # down
    ("100", "103.2", "100", "103"),  # up-cross -> proposal (bar 24)
    ("103", "103", "99.8", "100"),  # down
    ("100", "103.2", "100", "103"),  # up-cross -> proposal (bar 26)
    ("103", "103", "99.8", "100"),  # down
    ("100", "103.2", "100", "103"),  # up-cross -> proposal (bar 28)
]


def _long_then(
    followups: list[tuple[str, str, str, str]], *, minutes: int = _BASE_TF_MINUTES
) -> list[dict[str, Any]]:
    """20 flat look-back bars at 90, an upside breakout (long @102), then the follow-ups.

    Same real ``ta.sma`` cross entry the F-07d fixtures use (F-24: the breakout proxy is
    unreachable in a real RUN, so no fixture may depend on it).

    The look-back sits at 90, not 100, for the reason ``test_backtest_scaling._long_then``
    documents: once a follow-up closes back UNDER the entry MA it is an opposite signal
    that closes the position (the §9 rule) before the later layers can trigger. Parking the
    MA well below the whole oscillation keeps the ladder — not a trend break — the only
    thing governing the position's life, which is what this module is testing.
    """
    bars = [_bar(i, "90", "90", "90", "90") for i in range(20)]
    bars.append(_bar(20, "90", "103", "90", "102"))  # breakout -> long @102
    return bars + [_bar(21 + i, *ohlc) for i, ohlc in enumerate(followups)]


def _run(
    config: StrategyConfig,
    bars: list[dict[str, Any]],
    *,
    plan: IndicatorPlan | None = None,
    batch: int = 8,
    timeframe: str | None = None,
) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_s5c",
        indicator_plan=plan if plan is not None else _scale_plan(),
        # GH #547: increasing_by_layer resolves its rungs from the RUN's pinned bar
        # timeframe (a run-level fact, not a config field), so the tests that drive that
        # mode pass it the way the worker does. ``None`` reproduces every pre-#547 call.
        timeframe=timeframe,
    )


def _events(out: EngineOutput, kind: str) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == kind]


# --------------------------------------------------------------------------- #
# Schema — the typed ladder (doc 02 §5.7)                                      #
# --------------------------------------------------------------------------- #


def test_scaling_timeframe_mode_defaults_stay_backward_compatible() -> None:
    """A config saved before S5c parses unchanged and keeps the pre-S5c ladder."""
    scaling = _config(scaling=_scaling()).scaling_logic
    assert scaling is not None
    assert scaling.timeframe_mode == "same_strategy"
    assert scaling.custom_timeframe_sequence is None
    # The flat timeframe field is untouched by this slice.
    assert scaling.timeframe == "same_as_base_tf"


def test_scaling_custom_sequence_is_required_for_the_custom_sequence_mode() -> None:
    with pytest.raises(ValidationError, match="Custom timeframe sequence required"):
        _config(scaling=_scaling(timeframe_mode="custom_sequence"))
    # An explicitly EMPTY sequence is the same defect, not an "unbounded ladder".
    with pytest.raises(ValidationError, match="Custom timeframe sequence required"):
        _config(scaling=_scaling(timeframe_mode="custom_sequence", custom_timeframe_sequence=[]))


def test_scaling_custom_sequence_is_dropped_under_the_other_modes() -> None:
    """Switching the mode back must not leave a stale ladder in the saved revision."""
    for mode in ("same_strategy", "increasing_by_layer"):
        scaling = _config(
            scaling=_scaling(timeframe_mode=mode, custom_timeframe_sequence=["15m", "1h"])
        ).scaling_logic
        assert scaling is not None
        assert scaling.custom_timeframe_sequence is None, mode


def test_scaling_custom_sequence_must_be_strictly_increasing() -> None:
    # Descending contradicts both the feature name and the V18 seed "15m > 30m > 1h > 4h".
    with pytest.raises(ValidationError, match="strictly increasing"):
        _config(
            scaling=_scaling(
                timeframe_mode="custom_sequence", custom_timeframe_sequence=["1h", "15m"]
            )
        )
    # A REPEATED rung makes two layers indistinguishable — the same defect, not a shortcut.
    with pytest.raises(ValidationError, match="strictly increasing"):
        _config(
            scaling=_scaling(
                timeframe_mode="custom_sequence", custom_timeframe_sequence=["1h", "1h"]
            )
        )
    # The V18 seed itself is accepted.
    scaling = _config(
        scaling=_scaling(
            timeframe_mode="custom_sequence",
            custom_timeframe_sequence=["15m", "30m", "1h", "4h"],
        )
    ).scaling_logic
    assert scaling is not None
    assert scaling.custom_timeframe_sequence == ["15m", "30m", "1h", "4h"]


def test_scaling_custom_sequence_is_a_typed_enum_not_a_free_string() -> None:
    """doc 02 §5.7: 'Typed array of canonical timeframe enums, not free string.'"""
    with pytest.raises(ValidationError):
        _config(
            scaling=_scaling(timeframe_mode="custom_sequence", custom_timeframe_sequence=["7m"])
        )


def test_scaling_canonical_timeframes_match_the_engine_ladder() -> None:
    """The config module cannot import the engine, so the two ladders are pinned equal.

    A rung added to ``indicators._TF_SECONDS`` but not to ``CANONICAL_TIMEFRAMES`` would
    silently make a sequence entry unbucketable (``layer_bucket`` -> None -> never a
    decision point), which is a stuck ladder rather than a loud error.
    """
    assert all(timeframe_seconds(tf) is not None for tf in CANONICAL_TIMEFRAMES)
    spans = [timeframe_seconds(tf) for tf in CANONICAL_TIMEFRAMES]
    assert spans == sorted(spans), "CANONICAL_TIMEFRAMES must be ascending by span"


# --------------------------------------------------------------------------- #
# Predicate — shared source of truth (readiness + engine)                      #
# --------------------------------------------------------------------------- #


def test_predicate_logic_based_scaling_and_custom_sequence_leave_the_fail_closed_set() -> None:
    assert scaling_is_modelled(_config(scaling=_scaling()))
    assert scaling_is_modelled(
        _config(
            scaling=_scaling(
                timeframe_mode="custom_sequence", custom_timeframe_sequence=["1h", "4h"]
            )
        )
    )


def test_predicate_increasing_by_layer_is_modelled() -> None:
    """GH #547 lifted the mode: doc 02 §6.1 fixes the rung (index + 1) and the signed
    exhaustion decision fixes the top (the ladder runs out at 1D, custom_sequence
    precedent) — nothing is guessed any more.

    DELIBERATE INVERSION of ``test_predicate_increasing_by_layer_stays_fail_closed``:
    that test's own docstring said the blocker existed because the rung and the top were
    undeclared; both are now declared and shipped, so keeping it red-pinned would pin the
    absence of the feature. The mode also counts as a DECLARED depth for the logic ladder
    (second assertion): the canonical ladder is finite, so like a custom sequence it
    bounds what ``max_scaling_layers`` alone otherwise must.
    """
    assert scaling_is_modelled(_config(scaling=_scaling(timeframe_mode="increasing_by_layer")))
    assert scaling_is_modelled(
        _config(scaling=_scaling(timeframe_mode="increasing_by_layer", max_layers=None))
    )


def test_predicate_unbounded_logic_ladder_stays_fail_closed() -> None:
    """Logic-based scaling has no ``layers`` field of its own (§5.7 gives depth to price).

    With neither ``max_scaling_layers`` nor a custom sequence there is no DECLARED depth,
    and a ladder that adds a layer on every signal edge for the life of the position is not
    something to run on a guess. A sequence alone is enough to bound it.
    """
    assert not scaling_is_modelled(_config(scaling=_scaling(max_layers=None)))
    assert scaling_is_modelled(
        _config(
            scaling=_scaling(
                max_layers=None,
                timeframe_mode="custom_sequence",
                custom_timeframe_sequence=["1h", "4h"],
            )
        )
    )


def test_predicate_logic_ladder_needs_blocks_and_a_positive_add_size() -> None:
    assert not scaling_is_modelled(_config(scaling=_scaling(add_size_value=None)))
    no_blocks = _scaling()
    no_blocks["logic_scaling"] = {"indicator_blocks": []}
    assert not scaling_is_modelled(_config(scaling=no_blocks))


# --------------------------------------------------------------------------- #
# Helpers — the closed-bar bucketing                                           #
# --------------------------------------------------------------------------- #


def test_layer_timeframe_walks_the_sequence_and_runs_out_rather_than_ungating() -> None:
    config = _config(
        scaling=_scaling(timeframe_mode="custom_sequence", custom_timeframe_sequence=["15m", "1h"])
    )
    assert layer_timeframe(config, 0) == "15m"
    assert layer_timeframe(config, 1) == "1h"
    # Past the end: no ladder left. The engine caps layers at the sequence length so this
    # is unreachable there, but a future caller that forgets the cap gets no free layer.
    assert layer_timeframe(config, 2) is None
    # same_strategy is ungated at every index.
    assert layer_timeframe(_config(scaling=_scaling()), 0) is None


def test_layer_timeframe_walks_the_canonical_ladder_from_the_run_base() -> None:
    """GH #547: layer N is decided on ``CANONICAL_TIMEFRAMES[index(base) + N]``.

    Doc 02 §6.1's own worked example — base 15m, then 30m, then 1h. The base is the RUN's
    pinned bar timeframe, passed by the caller; layer 0 filled means the NEXT layer is
    layer 1, one rung above the base.
    """
    config = _config(scaling=_scaling(timeframe_mode="increasing_by_layer"))
    assert layer_timeframe(config, 0, base_timeframe="15m") == "30m"
    assert layer_timeframe(config, 1, base_timeframe="15m") == "1h"
    assert layer_timeframe(config, 2, base_timeframe="15m") == "2h"
    # The top of the ladder: base 4h has exactly one rung above it. Past it: no ladder
    # left (the signed exhaustion decision) — the engine's depth cap makes this branch
    # unreachable, and like custom_sequence it is re-checked here anyway.
    assert layer_timeframe(config, 0, base_timeframe="4h") == "1D"
    assert layer_timeframe(config, 1, base_timeframe="4h") is None
    # No pinned bar timeframe / a base off the canonical ladder: no rung resolves. The
    # engine never consults this branch either (``increasing_ladder_depth`` is 0 there).
    assert layer_timeframe(config, 0) is None
    assert layer_timeframe(config, 0, base_timeframe="7m") is None
    # The base being passed changes NOTHING for the other two modes.
    assert layer_timeframe(_config(scaling=_scaling()), 0, base_timeframe="15m") is None
    seq_config = _config(
        scaling=_scaling(timeframe_mode="custom_sequence", custom_timeframe_sequence=["1h"])
    )
    assert layer_timeframe(seq_config, 0, base_timeframe="15m") == "1h"


def test_increasing_ladder_depth_counts_the_rungs_above_the_base() -> None:
    """The increasing_by_layer analogue of ``len(custom_timeframe_sequence)``.

    This is the number the engine caps the ladder at, so exhaustion is enforced by the
    same mechanism custom_sequence uses (layer count bound, past-the-end unreachable).
    Depth 0 — the top rung itself, an unknown base, an off-ladder base — means the
    position still opens and trades; it just never scales.
    """
    assert increasing_ladder_depth("1m") == len(CANONICAL_TIMEFRAMES) - 1
    assert increasing_ladder_depth("15m") == 5
    assert increasing_ladder_depth("4h") == 1
    assert increasing_ladder_depth("1D") == 0
    assert increasing_ladder_depth(None) == 0
    assert increasing_ladder_depth("7m") == 0


def test_layer_bucket_matches_the_multi_timeframe_indicator_convention() -> None:
    """floor(epoch / span) — the same bucketing ``indicators._htf_bucket`` uses."""
    hour_ms = 3_600_000
    assert layer_bucket(0, "1h") == 0
    assert layer_bucket(hour_ms - 1, "1h") == 0  # still inside the first candle
    assert layer_bucket(hour_ms, "1h") == 1  # the candle closed -> new bucket
    # Ungated / unplaceable / unrecognized all give None (fail closed for a gated ladder).
    assert layer_bucket(hour_ms, None) is None
    assert layer_bucket(None, "1h") is None
    assert layer_bucket(hour_ms, "7m") is None


# --------------------------------------------------------------------------- #
# Engine BEHAVIOUR — the config must change what the replay does               #
# --------------------------------------------------------------------------- #


def test_logic_ladder_adds_a_layer_on_every_signal_edge_when_ungated() -> None:
    """The same_strategy baseline: every up-cross of the scaling MA proposes a layer."""
    out = _run(_config(scaling=_scaling()), _long_then(_OSCILLATION))
    added = _events(out, "scale_layer_added")
    assert len(added) == 4, "four up-crosses, cap of four"
    assert all(e["method"] == "logic_based_scaling" for e in added)
    # An ungated ladder states no layer timeframe rather than implying one.
    assert all(e["layer_timeframe"] is None for e in added)


def test_custom_sequence_gates_layers_on_their_own_closed_candle() -> None:
    """The BEHAVIOUR proof: same bars, same signals, different fills.

    Every up-cross bar is a scaling proposal, so the only thing that can suppress a layer
    is the per-layer closed-bar gate. With 15m base bars and a 1h first rung, the proposals
    inside the entry bar's own hour are not decision points.
    """
    bars = _long_then(_OSCILLATION)
    gated = _run(
        _config(
            scaling=_scaling(
                timeframe_mode="custom_sequence", custom_timeframe_sequence=["1h", "4h"]
            )
        ),
        bars,
    )
    ungated = _run(_config(scaling=_scaling()), bars)

    gated_added = _events(gated, "scale_layer_added")
    ungated_added = _events(ungated, "scale_layer_added")
    assert len(gated_added) < len(ungated_added), (
        "a coarser per-layer timeframe must fill FEWER layers over the same signal path"
    )
    # Whatever did fill states the timeframe whose closed candle authorized it.
    assert [e["layer_timeframe"] for e in gated_added] == ["1h", "4h"][: len(gated_added)]


def test_custom_sequence_length_bounds_the_ladder() -> None:
    """The sequence length is itself a layer bound — no past-the-end rule is invented.

    The global cap allows four layers, but a one-entry sequence describes one layer, so the
    run stops there instead of repeating the last rung or falling back to the base
    timeframe (either would be a guess the spec does not license).
    """
    out = _run(
        _config(
            scaling=_scaling(timeframe_mode="custom_sequence", custom_timeframe_sequence=["15m"])
        ),
        _long_then(_OSCILLATION),
    )
    added = _events(out, "scale_layer_added")
    assert len(added) <= 1
    assert all(e["layer_timeframe"] == "15m" for e in added)


def test_price_distance_ladder_ignores_the_sequence() -> None:
    """The §5.7-table vs. §6.1-panel adjudication, as an executable assertion.

    doc 02 §6.1: "Price-Distance Based Scaling doğrudan fiyat mesafesiyle tetiklendiğinden
    bu timeframe dizisini kullanmaz." A price comparison evaluates no indicator, so it has
    no candle to close on — attaching a sequence to it must therefore change NOTHING.
    """
    bars = _long_then(_OSCILLATION)
    plain = _run(_config(scaling=_scaling(method="price_distance_scaling")), bars)
    sequenced = _run(
        _config(
            scaling=_scaling(
                method="price_distance_scaling",
                timeframe_mode="custom_sequence",
                custom_timeframe_sequence=["4h"],
            )
        ),
        bars,
    )
    plain_added = _events(plain, "scale_layer_added")
    assert [e["layer_timeframe"] for e in plain_added] == [None] * len(plain_added)
    # A 4h rung would suppress almost everything if it were (wrongly) applied here.
    assert [e["reference"] for e in _events(sequenced, "scale_layer_added")] == [
        e["reference"] for e in plain_added
    ]


def test_increasing_by_layer_gates_each_layer_one_rung_above_the_base() -> None:
    """GH #547 BEHAVIOUR proof: same bars, same signals, different fills.

    DELIBERATE INVERSION of ``test_increasing_by_layer_opens_no_position_at_all`` — that
    test pinned the fail-closed refusal of an unspecified ladder, and the ladder is now
    specified (rung signed by canon, top signed by the product owner), so the mode must
    TRADE. With 15m base bars the up-cross at bar 22 (5:30, a fresh 30m candle) fills
    layer 1 on ``30m``; the ladder then re-anchors in 1h buckets, so the next fill waits
    for bar 24 (6:00) and states ``1h``; layer 3 would need a fresh 2h candle and the
    remaining up-crosses (6:30, 7:00) sit inside the 6:00 bucket — so the coarsening rung
    itself is what suppresses them, not the layer cap.
    """
    bars = _long_then(_OSCILLATION)
    gated = _run(
        _config(scaling=_scaling(timeframe_mode="increasing_by_layer")), bars, timeframe="15m"
    )
    ungated = _run(_config(scaling=_scaling()), bars, timeframe="15m")

    gated_added = _events(gated, "scale_layer_added")
    ungated_added = _events(ungated, "scale_layer_added")
    assert len(ungated_added) == 4, "the same signal path proposes four layers ungated"
    # Each fill states the rung whose closed candle authorized it — one rung per layer
    # above the 15m base, doc 02 §6.1's own 15m -> 30m -> 1h walk.
    assert [e["layer_timeframe"] for e in gated_added] == ["30m", "1h"]
    assert len(gated_added) < len(ungated_added), (
        "the coarsening per-layer timeframe must fill FEWER layers over the same signals"
    )


def test_increasing_by_layer_ladder_runs_out_at_the_top_rung() -> None:
    """The signed GH #547 exhaustion decision, as behaviour: past 1D there is NO ladder.

    A 1D-based run has zero rungs above it, so with the SAME signal path that fills four
    layers under same_strategy, the increasing ladder fills none — and the position still
    opens and closes normally (this is exhaustion, not the fail-closed capability gate:
    nothing else about the run is inert). No layer is rejected either — a rung that does
    not exist is never a candidate, which is exactly how custom_sequence runs out.
    """
    daily = _long_then(_OSCILLATION, minutes=24 * 60)
    # Close the position at the end so the round trip is observable in ``trades``: a bar
    # back under the entry MA is an opposite signal (the §9 rule closes on it).
    daily.append(_bar(29, "100", "100", "60", "60", minutes=24 * 60))
    out = _run(
        _config(scaling=_scaling(timeframe_mode="increasing_by_layer")), daily, timeframe="1D"
    )
    assert _events(out, "scale_layer_added") == []
    assert _events(out, "scale_layer_rejected") == []
    assert len(out.trades) == 1, "exhaustion must not stop the position itself from trading"

    # The control: the same daily bars under same_strategy DO scale — proving the empty
    # ladder above is the rung bound at work, not a signal path that never proposed.
    control = _run(_config(scaling=_scaling()), daily, timeframe="1D")
    assert len(_events(control, "scale_layer_added")) == 4


def test_increasing_by_layer_without_a_pinned_bar_timeframe_never_scales() -> None:
    """HONEST BOUNDARY: an un-timeframed revision resolves no rung — depth 0, no layers.

    ``get_base_timeframe_for_revision`` returns None for an event-based or
    resolution-less revision, and the mode's rung is DEFINED relative to the base, so
    there is nothing to gate on. The run is NOT fail-closed (the position trades); the
    ladder is simply exhausted from layer 1. Readiness cannot see this — the predicate
    reads only the StrategyConfig — so the engine's depth cap is the load-bearing guard.
    """
    bars = _long_then(_OSCILLATION)
    bars.append(_bar(29, "100", "100", "60", "60"))
    out = _run(_config(scaling=_scaling(timeframe_mode="increasing_by_layer")), bars)
    assert _events(out, "scale_layer_added") == []
    assert len(out.trades) == 1


def test_logic_ladder_requires_a_signal_edge_not_a_held_signal() -> None:
    """A scaling signal that merely STAYS true must not add a layer on every bar.

    Mirrors the F-07e conflict edge detector. Without this the layer cap alone would decide
    how many layers a single sustained signal produced, which is a cap doing a rule's job.
    """
    held = IndicatorPlan(
        entry_rule=_scale_plan().entry_rule,
        entry_specs=_scale_plan().entry_specs,
        scale_specs=(
            IndicatorSpec(
                block_id="sc_1",
                canonical_key="ta.sma",
                length=3,
                direction="long",
                requirement="required",
                validity="until_opposite_signal",
            ),
        ),
        scale_rule=SignalRule(rule="required_indicator_blocks_only"),
    )
    out = _run(_config(scaling=_scaling()), _long_then(_OSCILLATION), plan=held)
    added = _events(out, "scale_layer_added")
    assert len(added) < 4, "a held signal must not spend the whole layer budget on one edge"


def test_gated_ladder_still_books_one_position_with_a_weighted_basis() -> None:
    """The gate changes WHEN layers fill, not the single-position accounting invariant."""
    out = _run(
        _config(
            scaling=_scaling(
                timeframe_mode="custom_sequence", custom_timeframe_sequence=["1h", "4h"]
            )
        ),
        _long_then(_OSCILLATION),
    )
    added = _events(out, "scale_layer_added")
    assert added, "this fixture must fill at least one gated layer to be meaningful"
    for event in added:
        # A layer folds into the SAME lifecycle and grows the single position.
        assert event["position_seq"] == 1
        assert Decimal(event["new_size"]) > Decimal("50")


# --------------------------------------------------------------------------- #
# Manifest — the execution_key namespace shift (INF-04/INF-05)                 #
# --------------------------------------------------------------------------- #


def _manifest(engine_version: str):
    return build_run_manifest(
        run_id="btrun_s5c",
        composition_id="mbws_1",
        composition_snapshot_id="snap_A",
        composition_fingerprint="fp_1",
        item_manifest={
            "items": [
                {
                    "item_id": "mbi_1",
                    "kind": "strategy",
                    "root_id": "wo_a",
                    "revision_id": "rev_a",
                    "position": 10,
                    "enabled": True,
                }
            ]
        },
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_1",
        created_at_iso="2024-01-01T00:00:00Z",
        engine_version=engine_version,
    )


def test_scaling_timeframe_mode_shifts_the_execution_key_namespace() -> None:
    """The same run pinned to two engine versions must not share an execution_key.

    NOTE the deliberate absence of ``assert ENGINE_VERSION == "<literal>"``: the shift is
    what matters, and a literal here would re-break on the next bump (as S5a's copy did).
    """
    current = _manifest(ENGINE_VERSION)
    prior = _manifest(_PRIOR_ENGINE_VERSION)
    assert current.manifest["identity"]["engine_version"] == ENGINE_VERSION
    # An engine that could not evaluate a logic ladder or a per-layer timeframe must never
    # share this namespace...
    assert current.execution_key != prior.execution_key
    # ...while the same pin reproduces the same key.
    assert current.execution_key == _manifest(ENGINE_VERSION).execution_key
