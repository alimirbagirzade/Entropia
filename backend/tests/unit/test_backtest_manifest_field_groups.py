"""K-04 — the Run Manifest carries all SEVEN doc 15 §9.2 field groups.

Pure builder-level proof: the three groups that only exist behind a dereference
(strategy/package, external object, data/time) are recorded in the manifest AND are
part of the reproducibility content, so two runs whose transitive package / dataset /
import revisions differ can never share an ``execution_key`` (INF-04/INF-05). The DB
resolution + the worker's fail-closed re-resolution are covered by
``tests/integration/test_backtest_persistence.py``.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.backtest.manifest import build_run_manifest

_ITEM_MANIFEST = {
    "items": [
        {
            "item_id": "mbi_1",
            "kind": "strategy",
            "root_id": "woroot_1",
            "revision_id": "worev_1",
            "position": 0,
            "enabled": True,
        }
    ]
}


def _strategy_context(package_revision_id: str = "pkgrev_1") -> list[dict[str, Any]]:
    return [
        {
            "item_id": "mbi_1",
            "work_object_revision_id": "worev_1",
            "strategy_revision_id": "strev_1",
            "strategy_root_id": "strat_root_1",
            "rationale_family_id": "rf_1",
            "package_revisions": [
                {
                    "role": "entry",
                    "block_id": "ib_1",
                    "condition_block_id": None,
                    "leg_index": None,
                    "package_root_id": "pkg_root_1",
                    "package_revision_id": package_revision_id,
                    "pinned_content_hash": "b" * 64,
                    "parameter_overrides": {"length": 14},
                    "revision": {
                        "package_kind": "indicator",
                        "content_hash": "c" * 64,
                        "validation_state": "passed",
                        "approval_state": "approved",
                    },
                }
            ],
            "resolver_revisions": [
                {
                    "canonical_key": "ta.sma",
                    "embedded_entity_id": "esp_1",
                    "embedded_revision_id": "esprev_1",
                    "content_hash": "d" * 64,
                    "runtime_adapter": "python",
                    "registry_version": "1",
                }
            ],
        }
    ]


def _external_context() -> list[dict[str, Any]]:
    return [
        {
            "item_id": "mbi_2",
            "item_kind": "trading_signal",
            "work_object_revision_id": "worev_2",
            "import_binding": {
                "source_asset_id": "srcast_1",
                "normalized_event_revision_id": "nsev_1",
                "mapping_revision_id": None,
            },
            "time_policy": {
                "source_timezone": "Europe/Istanbul",
                "normalization_timezone": "UTC",
                "availability_rule": "row_available_time",
            },
            "price_policy": {"source": "signal_price", "fallback": None},
            "ohlcv_policy": {"use_mode": "reference_only"},
            "data_quality": {"mode": "strict"},
            "event_model": {"resolution_kind": "bar", "base_timeframe": "1m"},
            "normalized_event_revision": {
                "normalized_event_revision_id": "nsev_1",
                "source_asset_id": "srcast_1",
                "status": "succeeded",
                "instrument_id": "BTCUSDT",
                "accepted_count": 3,
                "skipped_count": 0,
                "content_hash": "e" * 64,
                "earliest_available_time": "2024-02-01T00:00:00+00:00",
                "validation_summary": {"source_timezone": "Europe/Istanbul"},
            },
        }
    ]


def _data_time_context(market_revision_id: str = "mdrev_1") -> list[dict[str, Any]]:
    return [
        {
            "item_id": "mbi_1",
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "mdroot_1",
            "market_dataset_revision_id": market_revision_id,
            "pinned_content_hash": "a" * 64,
            "market_dataset": {
                "entity_id": "mdroot_1",
                "revision_state": "approved",
                "market_data_type": "ohlcv",
                "resolution_kind": "bar",
                "resolution_value": "1m",
                "timezone_mode": "explicit",
                "timezone_iana": "UTC",
                "record_time_basis": "open_time",
                "instrument_id": "BTCUSDT",
                "content_hash": "a" * 64,
            },
            "coverage": {
                "start_at": "2024-02-01T00:00:00+00:00",
                "end_at": "2024-02-22T00:00:00+00:00",
                "row_count": 22,
                "slice_count": 1,
            },
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_open"},
            "research_dataset_revision_ids": ["rdrev_1"],
            "research_datasets": [
                {
                    "role": "funding",
                    "root_id": "rdroot_1",
                    "revision_id": "rdrev_1",
                    "pinned_content_hash": "f" * 64,
                    "revision": {
                        "entity_id": "rdroot_1",
                        "revision_state": "approved",
                        "category_key": "funding_rate",
                        "usage_scope": "research_backtest",
                        "content_hash": "f" * 64,
                        "available_time_policy": "event_time_plus_delay",
                        "available_delay_seconds": 60,
                        "event_time_semantics": "point_in_time",
                        "frequency_policy": "irregular",
                        "source_timezone_mode": "explicit",
                        "source_timezone_iana": "UTC",
                        "linked_market_dataset_revision_id": "mdrev_1",
                        "instrument_mapping_ref": "BTCUSDT",
                        "field_definition_version": 1,
                        "feature_definitions": [],
                    },
                }
            ],
        }
    ]


def _build(
    *,
    strategy_package: list[dict[str, Any]] | None = None,
    external_objects: list[dict[str, Any]] | None = None,
    data_time: list[dict[str, Any]] | None = None,
):
    return build_run_manifest(
        run_id="btrun_1",
        composition_id="mbws_1",
        composition_snapshot_id="mbsnap_1",
        composition_fingerprint="fp_1",
        item_manifest=_ITEM_MANIFEST,
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_1",
        created_at_iso="2024-03-01T00:00:00Z",
        strategy_package_context=strategy_package,
        external_object_context=external_objects,
        data_time_context=data_time,
    )


def test_manifest_carries_all_seven_field_groups() -> None:
    built = _build(
        strategy_package=_strategy_context(),
        external_objects=_external_context(),
        data_time=_data_time_context(),
    )
    manifest = built.manifest
    # doc 15 §9.2 — identity, mainboard items, strategy/package, external object,
    # data/time, capital/execution, result artifact.
    for group in (
        "identity",
        "mainboard_items",
        "strategy_package_context",
        "external_object_context",
        "data_time_context",
        "capital_execution",
        "result_artifact_context",
    ):
        assert manifest[group] is not None, group

    strategy = manifest["strategy_package_context"][0]
    assert strategy["strategy_revision_id"] == "strev_1"
    # Transitive: the pinned package AND the resolver (ESP) revision it froze.
    assert strategy["package_revisions"][0]["package_revision_id"] == "pkgrev_1"
    assert strategy["resolver_revisions"][0]["embedded_revision_id"] == "esprev_1"
    # Strategy-local parameter snapshot travels with its block.
    assert strategy["package_revisions"][0]["parameter_overrides"] == {"length": 14}

    external = manifest["external_object_context"][0]
    assert external["import_binding"]["normalized_event_revision_id"] == "nsev_1"
    assert external["time_policy"]["source_timezone"] == "Europe/Istanbul"
    assert external["price_policy"]["source"] == "signal_price"

    data_time = manifest["data_time_context"][0]
    assert data_time["market_dataset_revision_id"] == "mdrev_1"
    assert data_time["research_dataset_revision_ids"] == ["rdrev_1"]
    assert data_time["coverage"]["row_count"] == 22
    assert data_time["market_dataset"]["resolution_value"] == "1m"
    research = data_time["research_datasets"][0]["revision"]
    assert research["available_time_policy"] == "event_time_plus_delay"
    assert research["instrument_mapping_ref"] == "BTCUSDT"


def test_execution_key_shifts_when_a_transitive_package_pin_changes() -> None:
    # Same composition fingerprint + same Mainboard pins, but a different indicator
    # package revision behind the strategy: the runs replay different logic and must
    # never share an execution_key (INF-04/INF-05 idempotent reuse).
    a = _build(strategy_package=_strategy_context("pkgrev_1"), data_time=_data_time_context())
    b = _build(strategy_package=_strategy_context("pkgrev_2"), data_time=_data_time_context())
    assert (
        a.manifest["identity"]["composition_fingerprint"]
        == b.manifest["identity"]["composition_fingerprint"]
    )
    assert a.execution_key != b.execution_key


def test_execution_key_shifts_when_the_pinned_market_dataset_changes() -> None:
    a = _build(strategy_package=_strategy_context(), data_time=_data_time_context("mdrev_1"))
    b = _build(strategy_package=_strategy_context(), data_time=_data_time_context("mdrev_2"))
    assert a.execution_key != b.execution_key


def test_absent_context_is_an_explicit_null_not_a_fabricated_empty_set() -> None:
    # A caller that supplies no resolver must not make the manifest CLAIM an empty
    # dependency set — the honest value is null (nothing was resolved).
    built = _build()
    assert built.manifest["strategy_package_context"] is None
    assert built.manifest["external_object_context"] is None
    assert built.manifest["data_time_context"] is None
