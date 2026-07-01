"""Stage 5c — Arrange Metrics + export/artifact pure-domain unit tests (doc 17; doc-15).

No database. Covers the metric registry shape, selection normalization/validation,
config-hash + lock-transition classification, the opaque artifact cursor round-trip
+ tamper rejection, and the export checksum/provenance determinism.
"""

from __future__ import annotations

import pytest

from entropia.domain.backtest.artifacts import (
    ArtifactType,
    decode_artifact_cursor,
    encode_artifact_cursor,
    normalize_artifact_type,
)
from entropia.domain.backtest.export import (
    EXPORT_SCHEMA_VERSION,
    ExportFormat,
    ExportType,
    build_object_key,
    compute_export_checksum,
    normalize_export_format,
    normalize_export_type,
)
from entropia.domain.metric_profile.profile import (
    RegistrySnapshot,
    compute_config_hash,
    normalize_selection,
    transition_reason,
)
from entropia.domain.metric_profile.registry import (
    DEFAULT_SELECTED_METRIC_CODES,
    METRIC_REGISTRY,
    REGISTRY_VERSION,
)
from entropia.shared.errors import (
    ArtifactTypeInvalidError,
    CursorInvalidError,
    ExportFormatInvalidError,
    ExportTypeInvalidError,
    MetricCodeUnknownError,
    MetricNotSelectableError,
    MetricSelectionEmptyError,
)


def _snapshot() -> RegistrySnapshot:
    selectable = {
        row.metric_code: row.display_order
        for row in METRIC_REGISTRY
        if str(row.availability_status) == "selectable"
    }
    known = frozenset(row.metric_code for row in METRIC_REGISTRY)
    return RegistrySnapshot(selectable_order=selectable, known=known)


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #


def test_registry_has_nine_selectable_and_eighteen_future():
    selectable = [r for r in METRIC_REGISTRY if str(r.availability_status) == "selectable"]
    future = [r for r in METRIC_REGISTRY if str(r.availability_status) == "future"]
    assert len(selectable) == 9
    assert len(future) == 18
    assert len(METRIC_REGISTRY) == 27


def test_default_selection_is_nine_selectable_in_registry_order():
    assert DEFAULT_SELECTED_METRIC_CODES == (
        "net_profit",
        "max_drawdown",
        "romad",
        "win_rate",
        "profit_factor",
        "total_trades",
        "total_stops",
        "max_stop_streak",
        "total_winning_trades",
    )


# --------------------------------------------------------------------------- #
# Selection normalization + validation                                         #
# --------------------------------------------------------------------------- #


def test_normalize_selection_reorders_to_registry_order_and_dedupes():
    snap = _snapshot()
    out = normalize_selection(["romad", "net_profit", "romad", "win_rate"], snap)
    # deduped + sorted by registry display order (net_profit=0, romad=2, win_rate=3)
    assert out == ["net_profit", "romad", "win_rate"]


def test_normalize_selection_empty_raises():
    with pytest.raises(MetricSelectionEmptyError):
        normalize_selection([], _snapshot())


def test_normalize_selection_unknown_code_raises():
    with pytest.raises(MetricCodeUnknownError):
        normalize_selection(["net_profit", "does_not_exist"], _snapshot())


def test_normalize_selection_future_code_not_selectable():
    with pytest.raises(MetricNotSelectableError):
        normalize_selection(["net_profit", "sharpe_ratio"], _snapshot())


# --------------------------------------------------------------------------- #
# Config hash + transition                                                     #
# --------------------------------------------------------------------------- #


def test_config_hash_is_deterministic_and_order_sensitive():
    a = compute_config_hash(
        selected_metric_codes=["net_profit", "romad"], is_locked=False, registry_version="v1"
    )
    b = compute_config_hash(
        selected_metric_codes=["net_profit", "romad"], is_locked=False, registry_version="v1"
    )
    c = compute_config_hash(
        selected_metric_codes=["romad", "net_profit"], is_locked=False, registry_version="v1"
    )
    d = compute_config_hash(
        selected_metric_codes=["net_profit", "romad"], is_locked=True, registry_version="v1"
    )
    assert a == b
    assert a != c  # order matters
    assert a != d  # lock flag matters


def test_transition_reason_apply_lock_unlock():
    assert transition_reason(current_is_locked=None, next_is_locked=False) == "apply"
    assert transition_reason(current_is_locked=False, next_is_locked=False) == "apply"
    assert transition_reason(current_is_locked=False, next_is_locked=True) == "lock"
    assert transition_reason(current_is_locked=True, next_is_locked=False) == "unlock"


# --------------------------------------------------------------------------- #
# Artifact cursor                                                              #
# --------------------------------------------------------------------------- #


def test_artifact_cursor_round_trip():
    token = encode_artifact_cursor(ArtifactType.TRADE_LEDGER, last_key="42")
    decoded = decode_artifact_cursor(token, artifact_type=ArtifactType.TRADE_LEDGER)
    assert decoded.last_key == "42"


def test_artifact_cursor_rejects_wrong_type():
    token = encode_artifact_cursor(ArtifactType.TRADE_LEDGER, last_key="42")
    with pytest.raises(CursorInvalidError):
        decode_artifact_cursor(token, artifact_type=ArtifactType.EQUITY_CURVE)


def test_artifact_cursor_rejects_tampered_token():
    with pytest.raises(CursorInvalidError):
        decode_artifact_cursor("not-a-real-cursor!!", artifact_type=ArtifactType.TRADE_LEDGER)


def test_normalize_artifact_type_alias_and_unknown():
    assert normalize_artifact_type("ledger") is ArtifactType.TRADE_LEDGER
    assert normalize_artifact_type("equity_curve") is ArtifactType.EQUITY_CURVE
    with pytest.raises(ArtifactTypeInvalidError):
        normalize_artifact_type("bogus")


# --------------------------------------------------------------------------- #
# Export contract                                                              #
# --------------------------------------------------------------------------- #


def test_normalize_export_type_and_format():
    assert normalize_export_type("trade_ledger") is ExportType.TRADE_LEDGER
    assert normalize_export_format("csv") is ExportFormat.CSV
    with pytest.raises(ExportTypeInvalidError):
        normalize_export_type("nope")
    with pytest.raises(ExportFormatInvalidError):
        normalize_export_format("xlsx")


def test_export_checksum_is_deterministic_and_provenance_sensitive():
    rows = [{"seq": 1, "pnl": "10"}, {"seq": 2, "pnl": "-5"}]
    a = compute_export_checksum(
        export_type=ExportType.TRADE_LEDGER,
        fmt=ExportFormat.CSV,
        schema_version=EXPORT_SCHEMA_VERSION,
        source_manifest_hash="h1",
        rows=rows,
    )
    b = compute_export_checksum(
        export_type=ExportType.TRADE_LEDGER,
        fmt=ExportFormat.CSV,
        schema_version=EXPORT_SCHEMA_VERSION,
        source_manifest_hash="h1",
        rows=rows,
    )
    c = compute_export_checksum(
        export_type=ExportType.TRADE_LEDGER,
        fmt=ExportFormat.CSV,
        schema_version=EXPORT_SCHEMA_VERSION,
        source_manifest_hash="h2",  # different provenance
        rows=rows,
    )
    assert a == b
    assert a != c


def test_build_object_key_is_deterministic():
    key = build_object_key(
        result_id="btres_1",
        export_type=ExportType.TRADE_LEDGER,
        export_id="btexp_9",
        fmt=ExportFormat.CSV,
    )
    assert key == "exports/btres_1/trade_ledger/btexp_9.csv"


def test_registry_version_constant():
    assert REGISTRY_VERSION == "v1"
