"""Market dataset object-storage I/O (decision D5/D6, Module 20 §5).

Deterministic, content-addressed keys. The object key is NOT authoritative —
every artifact is mirrored by a PostgreSQL metadata row. No I/O happens at import
time (the client is built lazily by ``get_s3_client``), so this module is
importable without a live MinIO.
"""

from __future__ import annotations

import hashlib

from entropia.config import get_settings
from entropia.infrastructure.s3.client import get_s3_client

_RAW_PREFIX = "market/raw"
_PROCESSED_PREFIX = "market/processed"


def content_digest(data: bytes) -> str:
    """sha256 hex digest of the bytes — the content address."""
    return hashlib.sha256(data).hexdigest()


def raw_object_key(entity_id: str, digest: str) -> str:
    return f"{_RAW_PREFIX}/{entity_id}/{digest}"


def processed_object_key(entity_id: str, digest: str) -> str:
    return f"{_PROCESSED_PREFIX}/{entity_id}/{digest}.parquet"


def put_raw_bytes(
    entity_id: str, data: bytes, *, content_type: str | None = None
) -> tuple[str, str]:
    """Store raw upload bytes content-addressed. Returns ``(object_key, digest)``."""
    digest = content_digest(data)
    key = raw_object_key(entity_id, digest)
    bucket = get_settings().object_storage_bucket
    client = get_s3_client()
    if content_type:
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    else:
        client.put_object(Bucket=bucket, Key=key, Body=data)
    return key, digest


def get_raw_bytes(object_key: str) -> bytes:
    bucket = get_settings().object_storage_bucket
    resp = get_s3_client().get_object(Bucket=bucket, Key=object_key)
    body: bytes = resp["Body"].read()
    return body


def put_processed_parquet(entity_id: str, data: bytes) -> tuple[str, str]:
    """Store processed Parquet bytes content-addressed. Returns ``(object_key, digest)``."""
    digest = content_digest(data)
    key = processed_object_key(entity_id, digest)
    bucket = get_settings().object_storage_bucket
    get_s3_client().put_object(
        Bucket=bucket, Key=key, Body=data, ContentType="application/vnd.apache.parquet"
    )
    return key, digest


def get_processed_parquet(object_key: str) -> bytes:
    bucket = get_settings().object_storage_bucket
    resp = get_s3_client().get_object(Bucket=bucket, Key=object_key)
    body: bytes = resp["Body"].read()
    return body
