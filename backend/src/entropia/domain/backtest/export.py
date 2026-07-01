"""Result export contract: types, formats, provenance + deterministic checksum.

Stage 5c, doc-15 deferred (doc 15 §7 RequestResultExport, §9.1 ExportArtifact,
§14). An export is a schema-versioned DERIVATIVE of one immutable Result; the DB
row holds only metadata (object-storage key + checksum + schema_version +
row_count) and the PROVENANCE is the source Result's ``manifest_hash`` (doc 15
§9.1, §14 — "export manifest source manifest hash"). The bytes are produced
deterministically from the immutable source artifact so the same result + type +
format always yields the same checksum (idempotent, reproducible). V1 materializes
synchronously (the engine is a stub, artifacts are small); an async ExportJob is a
tracked later refinement (doc 15 §7 "large exports return export_job_id").
"""

from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Any

from entropia.shared.errors import ExportFormatInvalidError, ExportTypeInvalidError

EXPORT_SCHEMA_VERSION = "v1"


class ExportType(StrEnum):
    """The exportable Result artifacts (doc 15 §3.2 Result export actions)."""

    TRADE_LEDGER = "trade_ledger"
    EQUITY_CURVE = "equity_curve"
    SIGNAL_EVENTS = "signal_events"
    DIAGNOSTICS = "diagnostics"
    SUMMARY = "summary"


class ExportFormat(StrEnum):
    """Accepted export container formats (doc 15 §9.1 artifact schema)."""

    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"


def normalize_export_type(raw: str) -> ExportType:
    try:
        return ExportType(raw)
    except ValueError as exc:
        raise ExportTypeInvalidError() from exc


def normalize_export_format(raw: str) -> ExportFormat:
    try:
        return ExportFormat(raw)
    except ValueError as exc:
        raise ExportFormatInvalidError() from exc


def build_object_key(
    *, result_id: str, export_type: ExportType, export_id: str, fmt: ExportFormat
) -> str:
    """Deterministic object-storage key for the export bytes (doc 15 §9.1).

    The DB stores only this reference + checksum; the immutable bytes live in
    object storage (a real put/get adapter lands with the async ExportJob).
    """
    return f"exports/{result_id}/{export_type}/{export_id}.{fmt}"


def compute_export_checksum(
    *,
    export_type: ExportType,
    fmt: ExportFormat,
    schema_version: str,
    source_manifest_hash: str,
    rows: list[dict[str, Any]],
) -> str:
    """Content checksum over the canonical serialization of the source rows.

    Ties the checksum to the provenance (``source_manifest_hash``) + schema so a
    tampered or re-typed export cannot masquerade as another (doc 15 §14 integrity).
    """
    payload = {
        "export_type": str(export_type),
        "format": str(fmt),
        "schema_version": schema_version,
        "source_manifest_hash": source_manifest_hash,
        "rows": rows,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "ExportFormat",
    "ExportType",
    "build_object_key",
    "compute_export_checksum",
    "normalize_export_format",
    "normalize_export_type",
]
