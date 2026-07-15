"""F-05 — physical bar-stream range filter (DB-free, pure).

``filter_bars_by_range``/``parse_range_bound`` are pure over already-fetched raw
row dicts, so they are covered here without a database; the worker-boundary
wiring (instrument cross-check, empty-range reject, ENGINE_VERSION reproducibility)
is covered in ``tests/integration/test_backtest_persistence.py``.
"""

from __future__ import annotations

from entropia.application.queries.market_bars import filter_bars_by_range, parse_range_bound


def _bar(ts: str) -> dict[str, str]:
    return {"timestamp": ts, "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"}


def test_parse_range_bound_normalizes_z_suffix_to_utc() -> None:
    parsed = parse_range_bound("2024-01-01T00:00:00Z")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.isoformat() == "2024-01-01T00:00:00+00:00"


def test_parse_range_bound_treats_naive_timestamp_as_utc() -> None:
    naive = parse_range_bound("2024-01-01T00:00:00")
    offset_form = parse_range_bound("2024-01-01T00:00:00+00:00")
    assert naive is not None and offset_form is not None
    assert naive == offset_form


def test_parse_range_bound_rejects_unparseable_value() -> None:
    assert parse_range_bound("not-a-timestamp") is None
    assert parse_range_bound("2024-13-40T99:99:00Z") is None


def test_filter_keeps_only_bars_inside_inclusive_range() -> None:
    batches = [
        [_bar("2024-01-01T00:00:00Z"), _bar("2024-01-05T00:00:00Z")],
        [_bar("2024-01-10T00:00:00Z"), _bar("2024-01-15T00:00:00Z")],
    ]
    kept = list(
        filter_bars_by_range(
            iter(batches), start="2024-01-05T00:00:00Z", end="2024-01-10T00:00:00Z"
        )
    )
    flat = [row["timestamp"] for batch in kept for row in batch]
    assert flat == ["2024-01-05T00:00:00Z", "2024-01-10T00:00:00Z"]


def test_filter_drops_rows_with_unparseable_timestamp() -> None:
    batches = [[_bar("2024-01-05T00:00:00Z"), {**_bar("bad"), "timestamp": "bad"}]]
    kept = list(
        filter_bars_by_range(
            iter(batches), start="2024-01-01T00:00:00Z", end="2024-02-01T00:00:00Z"
        )
    )
    flat = [row["timestamp"] for batch in kept for row in batch]
    assert flat == ["2024-01-05T00:00:00Z"]


def test_filter_never_yields_empty_batches() -> None:
    batches = [[_bar("2024-01-01T00:00:00Z")], [_bar("2024-06-01T00:00:00Z")]]
    kept = list(
        filter_bars_by_range(
            iter(batches), start="2024-01-01T00:00:00Z", end="2024-01-31T00:00:00Z"
        )
    )
    assert len(kept) == 1  # the second (fully out-of-range) batch is never yielded


def test_filter_yields_nothing_for_a_fully_excluded_stream() -> None:
    batches = [[_bar("2024-06-01T00:00:00Z")]]
    kept = list(
        filter_bars_by_range(
            iter(batches), start="2024-01-01T00:00:00Z", end="2024-01-31T00:00:00Z"
        )
    )
    assert kept == []


def test_filter_yields_nothing_for_an_invalid_range() -> None:
    batches = [[_bar("2024-01-01T00:00:00Z")]]
    # end < start
    kept = list(
        filter_bars_by_range(
            iter(batches), start="2024-06-01T00:00:00Z", end="2024-01-01T00:00:00Z"
        )
    )
    assert kept == []
