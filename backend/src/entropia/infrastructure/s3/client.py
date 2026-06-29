"""S3-compatible object storage client (MinIO locally).

Object key is NOT authoritative identity — every artifact is mirrored by a
PostgreSQL metadata row. Keys are deterministic and content-addressed
(Module 20 §5). Domain artifact writers arrive in later stages.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from entropia.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


@lru_cache(maxsize=1)
def get_s3_client() -> S3Client:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        use_ssl=settings.object_storage_use_ssl,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def check_object_storage() -> bool:
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=get_settings().object_storage_bucket)
        return True
    except Exception:
        return False
