"""K-04 — the Run Manifest pins all SEVEN doc 15 §9.2 field groups (real database).

Auto-skips without PostgreSQL (see tests/integration/conftest.py). Covers:

* admission resolves the three previously-missing groups — strategy/package (the real
  strategy revision + its transitive indicator package + resolver/ESP refs), external
  object (the Trading Signal import revision + mapping/timezone/price policy) and
  data/time (the pinned market dataset revision, its resolution/timezone identity and
  the strategy's range + execution timing);
* the worker re-resolves those pins fail-closed: a market dataset root soft-deleted
  after admission FAILS the run with RUN_FAILED_MANIFEST_RESOLUTION and materializes NO
  Result, even though a newer approved revision for the same instrument exists — the
  worker never falls back to the current Package Library / a 'latest' dataset row
  (doc 15 §15, §16);
* the same fail-closed gate covers the transitive package pin.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
)
from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.models import BacktestResult, BacktestRun, EntityRegistry
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo
from entropia.shared.ids import new_id
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _e2e_bars,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_INSTRUMENT = "BTCUSDT"


def _signal_payload(source_asset_id: str, normalized_revision_id: str) -> dict[str, Any]:
    """A valid Trading Signal revision payload (doc 04 §9.2 shape)."""
    return {
        "kind": "trading_signal",
        "identity": {"display_name": "K-04 signal source"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": _INSTRUMENT, "display_symbol": _INSTRUMENT},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {"source_timezone": "Europe/Istanbul", "normalization_timezone": "UTC"},
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "normalized_event_revision_id": normalized_revision_id,
        },
    }


async def _attach_trading_signal(session, actor: Actor, workspace_id: str) -> dict[str, Any]:
    """Seed an accepted Trading Signal import + attach it to the composition.

    Rows are written through the SAME repositories the import worker uses, so Ready
    Check resolves a real accepted normalized revision (no object storage needed)."""
    asset = await ts_repo.create_source_asset(
        session,
        source_asset_id=new_id("srcast"),
        owner_principal_id=actor.principal_id,
        draft_id=None,
        object_key="signal/raw/k04/seed.csv",
        raw_asset_hash="9" * 64,
        size_bytes=128,
        content_type="text/csv",
        original_filename="signals.csv",
        uploaded_by_principal_id=actor.principal_id,
    )
    await session.flush()
    normalized = await ts_repo.create_normalized_revision(
        session,
        source_asset_id=asset.source_asset_id,
        job_id=None,
        status=NormalizedRevisionStatus.SUCCEEDED,
        instrument_id=_INSTRUMENT,
        accepted_count=2,
        skipped_count=0,
        events=[],
        skipped_rows=[],
        validation_summary={"source_timezone": "Europe/Istanbul", "mapping_hash": "7" * 64},
        earliest_available_time=None,
        content_hash="8" * 64,
        created_by_principal_id=actor.principal_id,
    )
    await session.flush()
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="trading_signal",
        payload=_signal_payload(asset.source_asset_id, normalized.normalized_revision_id),
        # doc 01 anti-lookahead: an external work object must declare when its data
        # became available; a past instant keeps the seeded composition Ready.
        available_time=datetime(2024, 1, 1, tzinfo=UTC),
    )
    ts_repo.link_normalized_to_revision(normalized, work_object["revision_id"])
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="trading_signal",
    )
    await session.commit()
    return {
        "revision_id": work_object["revision_id"],
        "normalized_revision_id": normalized.normalized_revision_id,
        "source_asset_id": asset.source_asset_id,
    }


async def _seed_newer_approved_dataset(session) -> str:
    """A newer APPROVED dataset revision for the same instrument (fallback bait).

    A 'latest approved revision for this instrument' fallback would resolve THIS row;
    the worker must never reach for it (doc 15 §15)."""
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "newer bars"},
        instrument_id=_INSTRUMENT,
    )
    revision.revision_state = MarketRevisionState.APPROVED
    revision.resolution_kind = ResolutionKind.BAR
    revision.resolution_value = "1m"
    await session.flush()
    md_repo.add_processed_asset(
        session,
        entity_id=root.entity_id,
        object_key=f"market/processed/{root.entity_id}/newer.parquet",
        content_digest="newer-bars",
        size_bytes=4096,
        revision_id=revision.revision_id,
        row_count=22,
    )
    await session.commit()
    return revision.revision_id


# --------------------------------------------------------------------------- #
# The manifest carries all seven groups                                       #
# --------------------------------------------------------------------------- #


async def test_manifest_carries_all_seven_field_groups(session) -> None:
    await _seed_principals(session)
    composition_id, _root, strategy_revision_id = await _ready_composition(
        session, USER1, base_tf="1m", market_instrument_id=_INSTRUMENT
    )
    signal = await _attach_trading_signal(session, USER1, composition_id)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    manifest = (await bt_repo.get_manifest_by_run(session, admit["run_id"])).manifest
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

    # Strategy / package: the pinned work-object revision, the indicator package the
    # engine dereferences, and the resolver ref that package froze.
    strategy = manifest["strategy_package_context"][0]
    assert strategy["work_object_revision_id"] == strategy_revision_id
    assert strategy["strategy_root_id"] == "strat_root_seed"
    entry_packages = [p for p in strategy["package_revisions"] if p["role"] == "entry"]
    assert len(entry_packages) == 1
    entry_package = entry_packages[0]
    assert entry_package["revision"]["package_kind"] == "indicator"
    assert entry_package["revision"]["approval_state"] == "approved"

    # External object: the import revision + its mapping/timezone/price-source policy.
    external = manifest["external_object_context"][0]
    assert external["item_kind"] == "trading_signal"
    assert external["work_object_revision_id"] == signal["revision_id"]
    assert (
        external["normalized_event_revision"]["normalized_event_revision_id"]
        == signal["normalized_revision_id"]
    )
    assert external["normalized_event_revision"]["status"] == "succeeded"
    assert external["time_policy"]["source_timezone"] == "Europe/Istanbul"
    assert external["price_policy"]["source"] == "suggested_signal_price"
    assert external["import_binding"]["source_asset_id"] == signal["source_asset_id"]

    # Data / time: the pinned dataset revision identity + execution resolution.
    data_time = manifest["data_time_context"][0]
    assert data_time["instrument_id"] == _INSTRUMENT
    assert data_time["market_dataset"]["resolution_value"] == "1m"
    assert data_time["market_dataset"]["revision_state"] == "approved"
    assert data_time["execution"]["entry_timing"] == "next_candle_open"
    assert data_time["backtest_range"]["start"] == "2024-01-01T00:00:00Z"
    # Funding is OFF on the seeded strategy, so NO research feed is claimed.
    assert data_time["research_dataset_revision_ids"] == []

    # The run still executes end to end with the richer manifest.
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"


# --------------------------------------------------------------------------- #
# Fail-closed re-resolution: no 'latest' fallback                             #
# --------------------------------------------------------------------------- #


async def test_soft_deleted_market_dataset_fails_the_run_without_latest_fallback(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session, USER1, market_instrument_id=_INSTRUMENT
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    manifest = (await bt_repo.get_manifest_by_run(session, admit["run_id"])).manifest
    pinned_revision_id = manifest["data_time_context"][0]["market_dataset_revision_id"]
    newer_revision_id = await _seed_newer_approved_dataset(session)
    assert newer_revision_id != pinned_revision_id

    # The pinned dataset root is soft-deleted AFTER admission (Ready Check already
    # passed) — the classic race the fail-closed gate exists for.
    pinned = await md_repo.get_revision(session, pinned_revision_id)
    root = await session.get(EntityRegistry, pinned.entity_id)
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_MANIFEST_RESOLUTION"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "failed" and run.result_id is None
    # No silent substitution: the newer approved revision was never used, and CR-03
    # holds — a failed run materializes no Result.
    assert pinned_revision_id in (run.failure_message or "")
    assert newer_revision_id not in (run.failure_message or "")
    assert await _count(session, BacktestResult) == 0
    # The historical manifest stays readable (doc 15 §16 soft-delete acceptance).
    assert (await bt_repo.get_manifest_by_run(session, admit["run_id"])) is not None


async def test_missing_transitive_package_pin_fails_the_run(session) -> None:
    """A package revision the manifest pins but that no longer resolves is terminal.

    Before K-04 the manifest recorded no transitive package pin at all, so this class
    of drift could only be caught later (or not at all)."""
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    stored = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    doc = dict(stored.manifest)
    groups = [dict(entry) for entry in doc["strategy_package_context"]]
    packages = [dict(pkg) for pkg in groups[0]["package_revisions"]]
    packages[0]["package_revision_id"] = "pkgrev_missing"
    groups[0]["package_revisions"] = packages
    doc["strategy_package_context"] = groups
    stored.manifest = doc
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_MANIFEST_RESOLUTION"
    assert await _count(session, BacktestResult) == 0
