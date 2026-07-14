"""Stage 5b unit tests — Results History sort registry + cursor + context diff (doc 16).

Pure, DB-free coverage of ``domain/backtest/history``: sort normalization (canonical
+ V18 alias + invalid), opaque keyset cursor round-trip + tamper rejection, and the
compare context extractor/diff (missing field -> "Not available", never fabricated).
"""

from __future__ import annotations

import pytest

from entropia.domain.backtest.history import (
    DEFAULT_SORT,
    Cursor,
    HistorySort,
    build_manifest_excerpt,
    decode_cursor,
    diff_manifest_contexts,
    encode_cursor,
    extract_manifest_context,
    normalize_sort_key,
)
from entropia.shared.errors import CursorInvalidError, InvalidSortKeyError

# --- sort normalization (doc 16 §5, §12) ---------------------------------- #


def test_none_maps_to_default_newest() -> None:
    assert normalize_sort_key(None) is DEFAULT_SORT
    assert DEFAULT_SORT is HistorySort.NEWEST_CURRENT


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("newest_current", HistorySort.NEWEST_CURRENT),
        ("net_profit_percent_desc", HistorySort.NET_PROFIT_PERCENT_DESC),
        ("max_drawdown_asc", HistorySort.MAX_DRAWDOWN_ASC),
        # V18 dropdown aliases (doc 16 §5 value map)
        ("newest", HistorySort.NEWEST_CURRENT),
        ("highestReturn", HistorySort.NET_PROFIT_PERCENT_DESC),
        ("highestRomad", HistorySort.ROMAD_DESC),
        ("lowestDrawdown", HistorySort.MAX_DRAWDOWN_ASC),
        ("highestWinrate", HistorySort.WIN_RATE_DESC),
        ("mostTrades", HistorySort.TOTAL_TRADES_DESC),
    ],
)
def test_normalize_accepts_canonical_and_v18_alias(raw: str, expected: HistorySort) -> None:
    assert normalize_sort_key(raw) is expected


def test_unknown_sort_raises_invalid_sort_key() -> None:
    # No silent fallback to a known enum (doc 16 §12).
    with pytest.raises(InvalidSortKeyError):
        normalize_sort_key("highest_sharpe")


# --- opaque keyset cursor (doc 16 §5) ------------------------------------- #


def test_cursor_roundtrip_metric_value() -> None:
    token = encode_cursor(
        HistorySort.NET_PROFIT_PERCENT_DESC, last_value="80.5", last_result_id="btres_2"
    )
    decoded = decode_cursor(token, sort=HistorySort.NET_PROFIT_PERCENT_DESC)
    assert decoded == Cursor(last_value="80.5", last_result_id="btres_2")


def test_cursor_roundtrip_null_tail() -> None:
    token = encode_cursor(HistorySort.ROMAD_DESC, last_value=None, last_result_id="btres_9")
    decoded = decode_cursor(token, sort=HistorySort.ROMAD_DESC)
    assert decoded.last_value is None and decoded.last_result_id == "btres_9"


def test_cursor_built_for_other_sort_is_rejected() -> None:
    # A cursor pinned to one sort must not be reused with a different query (doc 16 §12).
    token = encode_cursor(HistorySort.ROMAD_DESC, last_value="2.0", last_result_id="btres_1")
    with pytest.raises(CursorInvalidError):
        decode_cursor(token, sort=HistorySort.WIN_RATE_DESC)


def test_malformed_cursor_is_rejected() -> None:
    with pytest.raises(CursorInvalidError):
        decode_cursor("not-a-real-cursor!!", sort=HistorySort.NEWEST_CURRENT)


# --- compare context (doc 16 §8.3, §9.4) ---------------------------------- #


def test_extract_context_surfaces_missing_field_as_none() -> None:
    manifest = {
        "identity": {"engine_version": "backtest-engine-v1-stub", "composition_fingerprint": "fp1"},
        "execution_key": "ek1",
        "capital_execution": {"mode": "portfolio"},
    }
    ctx = extract_manifest_context(manifest)
    assert ctx["engine_version"] == "backtest-engine-v1-stub"
    assert ctx["execution_key"] == "ek1"
    assert ctx["composition_fingerprint"] == "fp1"
    assert ctx["allocation_context"] == {"mode": "portfolio"}
    # Market Data revision is not separately pinned in V1 -> honest None (never 0/blank).
    assert ctx["market_data_revision"] is None


def test_extract_context_handles_empty_manifest() -> None:
    ctx = extract_manifest_context(None)
    assert all(
        ctx[key] is None for key in ("engine_version", "execution_key", "market_data_revision")
    )


def test_diff_flags_differing_engine_version_and_marks_not_available() -> None:
    a = extract_manifest_context({"identity": {"engine_version": "v1"}, "execution_key": "ek"})
    b = extract_manifest_context({"identity": {"engine_version": "v2"}, "execution_key": "ek"})
    diff = diff_manifest_contexts(a, b)
    assert diff["context_differs"] is True
    assert diff["fields"]["engine_version"]["differs"] is True
    assert diff["fields"]["execution_key"]["differs"] is False
    # Both missing market data -> not flagged, rendered as "Not available".
    assert diff["fields"]["market_data_revision"]["differs"] is False
    assert diff["fields"]["market_data_revision"]["a"] == "Not available"


def test_diff_identical_contexts_reports_no_difference() -> None:
    ctx = extract_manifest_context(
        {
            "identity": {"engine_version": "v1", "composition_fingerprint": "fp"},
            "execution_key": "ek",
        }
    )
    diff = diff_manifest_contexts(ctx, dict(ctx))
    assert diff["context_differs"] is False
    assert all(not field["differs"] for field in diff["fields"].values())


# --- S7: manifest excerpt enrichment (doc 16 §8.2/§9.4, RH-09) ------------ #


def _manifest(
    *, engine: str = "v2", strat_rev: str = "srev-1", plan_rev: str | None = "plan-9"
) -> dict:
    """A synthetic pinned manifest mirroring ``build_run_manifest`` output shape."""
    capital: dict = {"enabled": True}
    if plan_rev is not None:
        capital["plan_revision_id"] = plan_rev
    return {
        "identity": {
            "engine_version": engine,
            "composition_fingerprint": "fp1",
            "composition_snapshot_id": "snap-1",
        },
        "mainboard_items": [
            {
                "item_id": "it-1",
                "item_kind": "strategy",
                "root_id": "strat-root",
                "selected_revision_id": strat_rev,
                "position": 0,
                "enabled": True,
            },
            {
                "item_id": "it-2",
                "item_kind": "trading_signal",
                "root_id": "ts-root",
                "selected_revision_id": "ts-rev-1",
                "position": 1,
                "enabled": True,
            },
        ],
        "capital_execution": capital,
        "result_artifact_context": {
            "metric_set_version": "metric-set-v1",
            "output_artifact_profile": "standard-v1",
        },
        "execution_key": "ek1",
    }


def test_extract_context_surfaces_pinned_strategy_refs_and_allocation() -> None:
    ctx = extract_manifest_context(_manifest(strat_rev="srev-7", plan_rev="plan-3"))
    assert ctx["strategy_revision_refs"] == [
        {
            "item_id": "it-1",
            "item_kind": "strategy",
            "root_id": "strat-root",
            "revision_id": "srev-7",
            "position": 0,
            "enabled": True,
        }
    ]
    assert ctx["portfolio_allocation_plan_revision_id"] == "plan-3"
    assert ctx["artifact_context"]["metric_set_version"] == "metric-set-v1"
    # Market data still not separately pinned -> honest None, carried transitively.
    assert ctx["market_data_revision"] is None


def test_diff_flags_differing_strategy_revision_transitive_market_data() -> None:
    # A Market Data change lands inside the strategy config -> a different pinned
    # strategy revision, which the compare flags (RH-09) even though the dedicated
    # market_data_revision row stays "Not available".
    a = extract_manifest_context(_manifest(strat_rev="srev-1"))
    b = extract_manifest_context(_manifest(strat_rev="srev-2"))
    diff = diff_manifest_contexts(a, b)
    assert diff["context_differs"] is True
    assert diff["fields"]["strategy_revision_refs"]["differs"] is True
    assert diff["fields"]["market_data_revision"]["differs"] is False
    assert diff["fields"]["market_data_revision"]["a"] == "Not available"


def test_diff_flags_differing_allocation_plan_revision() -> None:
    a = extract_manifest_context(_manifest(plan_rev="plan-1"))
    b = extract_manifest_context(_manifest(plan_rev="plan-2"))
    diff = diff_manifest_contexts(a, b)
    assert diff["fields"]["portfolio_allocation_plan_revision_id"]["differs"] is True
    assert diff["fields"]["portfolio_allocation_plan_revision_id"]["a"] == "plan-1"


def test_extract_context_no_allocation_plan_is_honest_none() -> None:
    ctx = extract_manifest_context(_manifest(plan_rev=None))
    assert ctx["portfolio_allocation_plan_revision_id"] is None


def test_build_excerpt_reads_pinned_refs_and_availability() -> None:
    excerpt = build_manifest_excerpt(
        _manifest(strat_rev="srev-5", plan_rev="plan-8"),
        result_id="res-1",
        completed_at_utc="2026-07-14T00:00:00+00:00",
        artifact_availability={"counts": {"trade": 3}, "any_available": True},
    )
    assert excerpt["result_id"] == "res-1"
    assert excerpt["composition_snapshot_id"] == "snap-1"
    assert [r["revision_id"] for r in excerpt["strategy_revision_refs"]] == ["srev-5"]
    assert [r["item_kind"] for r in excerpt["external_work_refs"]] == ["trading_signal"]
    assert excerpt["portfolio_allocation_plan_revision_id"] == "plan-8"
    assert excerpt["engine_contract_version"] == "v2"
    assert excerpt["execution_context"]["execution_key"] == "ek1"
    assert excerpt["completed_at_utc"] == "2026-07-14T00:00:00+00:00"
    assert excerpt["artifact_availability"]["any_available"] is True
    # Not separately pinned in the V1 manifest -> honest empty/null.
    assert excerpt["package_revision_refs"] == []
    assert excerpt["market_data_revision"] is None
    assert excerpt["research_data_revision_refs"] == []


def test_build_excerpt_handles_empty_manifest_honestly() -> None:
    excerpt = build_manifest_excerpt(
        None,
        result_id="res-2",
        completed_at_utc=None,
        artifact_availability={"counts": {}, "any_available": False},
    )
    assert excerpt["strategy_revision_refs"] == []
    assert excerpt["external_work_refs"] == []
    assert excerpt["composition_snapshot_id"] is None
    assert excerpt["engine_contract_version"] is None
    assert excerpt["portfolio_allocation_plan_revision_id"] is None
