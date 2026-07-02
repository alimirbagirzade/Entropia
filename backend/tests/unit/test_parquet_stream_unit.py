"""Unit: bounded Parquet batching contract (INF-12) — pure local I/O, no S3."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from entropia.infrastructure.s3.parquet_stream import iter_parquet_batches

ROWS = 50_000
BATCH = 8_192


def _write_bars(path: Path, rows: int = ROWS) -> None:
    pl.DataFrame(
        {
            "timestamp": [f"2026-01-01T00:{i % 60:02d}:00Z" for i in range(rows)],
            "open": [float(100 + i % 7) for i in range(rows)],
            "close": [float(101 + i % 5) for i in range(rows)],
            "volume": list(range(rows)),
        }
    ).write_parquet(path)


def test_batches_are_bounded_and_complete(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    _write_bars(path)

    batches = list(iter_parquet_batches(str(path), batch_size=BATCH))

    assert all(len(b) <= BATCH for b in batches)  # never one giant materialization
    assert len(batches) == -(-ROWS // BATCH)  # ceil(50_000 / 8_192) = 7
    assert sum(len(b) for b in batches) == ROWS
    assert batches[0][0]["timestamp"] == "2026-01-01T00:00:00Z"
    assert batches[-1][-1]["volume"] == ROWS - 1


def test_column_projection_reads_only_requested_fields(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    _write_bars(path, rows=100)

    batches = list(iter_parquet_batches(str(path), batch_size=64, columns=["close", "volume"]))

    assert sum(len(b) for b in batches) == 100
    assert set(batches[0][0].keys()) == {"close", "volume"}
