"""Batched Parquet reads for large processed assets (INF-12, Module 20 §5).

``get_processed_parquet`` materializes the whole object in memory — fine for
metadata-sized reads, wrong for large market revisions. This module keeps the
resident footprint bounded regardless of asset size: the S3 object is streamed
to a spooled temp file (spills to disk past the cap, never fully in RAM) and
handed to ``pyarrow.parquet.ParquetFile.iter_batches`` so consumers see one
bounded record batch at a time. Runs on the Data Worker plane, never in the
API process.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from typing import Any

import pyarrow.parquet as pq

from entropia.config import get_settings
from entropia.infrastructure.s3.client import get_s3_client

DEFAULT_BATCH_SIZE = 8_192
# Spool cap: small assets stay in memory, anything larger spills to disk.
_SPOOL_MAX_BYTES = 32 * 1024 * 1024


def iter_parquet_batches(
    source: Any, *, batch_size: int = DEFAULT_BATCH_SIZE, columns: list[str] | None = None
) -> Iterator[list[dict[str, Any]]]:
    """Yield rows from a Parquet path/file-like in bounded batches.

    Pure local I/O (no S3) so unit tests can cover the batching contract
    without infrastructure. Each yielded batch is at most ``batch_size`` rows.
    """
    parquet = pq.ParquetFile(source)
    for record_batch in parquet.iter_batches(batch_size=batch_size, columns=columns):
        yield record_batch.to_pylist()


def stream_processed_batches(
    object_key: str, *, batch_size: int = DEFAULT_BATCH_SIZE, columns: list[str] | None = None
) -> Iterator[list[dict[str, Any]]]:
    """Stream a processed S3 Parquet asset in bounded batches (INF-12)."""
    bucket = get_settings().object_storage_bucket
    with tempfile.SpooledTemporaryFile(max_size=_SPOOL_MAX_BYTES) as spool:
        get_s3_client().download_fileobj(Bucket=bucket, Key=object_key, Fileobj=spool)
        spool.seek(0)
        yield from iter_parquet_batches(spool, batch_size=batch_size, columns=columns)


__all__ = ["DEFAULT_BATCH_SIZE", "iter_parquet_batches", "stream_processed_batches"]
