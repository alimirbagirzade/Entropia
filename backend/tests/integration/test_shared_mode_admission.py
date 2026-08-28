"""ADR 0002 §13.1 OD-1(a) / OD-6(a) refused at admission, end to end.

`C6`'s plan-level half. The unit file
(``tests/unit/test_shared_mode_admission.py``) pins the decisions; this one proves
the WIRING — that a real ``request_backtest_run`` refuses, with the doc 14 §9.1
envelope, and leaves no run / manifest / job behind.

Why every test here lifts the flag
----------------------------------
While ``SHARED_ALLOCATION_STATUS`` is ``future_dev`` the containment guard refuses
EVERY shared run before these two are consulted, so an unlifted test would assert
nothing about them — it would re-prove containment. ``_lifted`` moves the world the
way ``tests/unit/test_shared_allocation_two_world_gate.py`` does, which is exactly
what makes the composition ADIM 52 recorded as unconstructible
(``test_external_object_run_provenance``'s "no test can construct it") constructible
here. ``test_containment_still_leads_in_the_shipped_world`` keeps the shipped
ordering honest.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.allocation import capability
from entropia.domain.allocation.shared_mode_admission import (
    DEFERRED_FILL_REMEDIATION,
    MIXED_RECORD_TIME_BASIS_REMEDIATION,
    NON_EXECUTING_ITEM_MESSAGE,
    NON_EXECUTING_ITEM_REMEDIATION,
    SCALING_REMEDIATION,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    VisibilityScope,
)
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    RecordTimeBasis,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    BacktestRunManifest,
    Job,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import ReadinessBlockedError
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _empty_composition,
    _seed_principals,
    _strategy_payload,
)
from tests.integration.test_external_object_run_provenance import _attach_trade_log

pytestmark = pytest.mark.integration

_IMMEDIATE_TIMING = {
    "entry_timing": "current_candle_close",
    "exit_timing": "current_candle_close",
}

_SCALING_ON: dict[str, Any] = {
    "enabled": True,
    "method": "price_distance_scaling",
    "price_scaling": {"retracement_distance": "1", "layers": 2},
    "add_size": "percent_of_initial",
    "add_size_value": "50",
}

_OD6 = "ALLOCATION_SHARED_MODE_NON_EXECUTING_ITEM"
_OD1 = "ALLOCATION_SHARED_MODE_MIXED_RECORD_TIME_BASIS"
_CONTAINMENT = "ALLOCATION_SHARED_MODE_NOT_IN_BUILD"
_G11 = "ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED"
_G12 = "ALLOCATION_SHARED_MODE_SCALING_UNSUPPORTED"


@contextmanager
def _lifted(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force the ``active_v1`` world for the duration of the block.

    Patching the module global reaches ``backtest_run.py`` without it importing
    anything from here: it holds a reference to the FUNCTION
    ``shared_allocation_is_executable``, whose ``__globals__`` is this module's dict.
    """
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        yield


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so the Trade Log upload + import worker run
    without MinIO. Same shape as the other integration suites' fixture; it is
    per-file there, so it is per-file here."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


# --------------------------------------------------------------------------- #
# Harness — the per-strategy block of ``_ready_composition``, twice, with a     #
# chosen ``record_time_basis`` on each pinned market revision.                  #
# --------------------------------------------------------------------------- #


async def _attach_ready_strategy(
    session,
    actor: Actor,
    workspace_id: str,
    *,
    basis: RecordTimeBasis | None = None,
    execution: dict[str, str] | None = _IMMEDIATE_TIMING,
    scaling: dict[str, Any] | None = None,
) -> None:
    """Attach one READY strategy pinning its own APPROVED market revision.

    Mirrors ``_ready_composition``'s builder rather than adding a rival one; what it adds
    is ``record_time_basis`` (which no existing builder can set, and which is the entire
    subject of OD-1) and the two knobs `C6`'s signed gates read.

    ``execution`` defaults to an IMMEDIATE timing, unlike ``_strategy_payload``'s own
    default. Every strategy in this file lives in a SHARED composition, and the seed
    payload's ``next_candle_open`` is precisely what G11 refuses — so a shared fixture
    built on the default would be refused for a reason no test in the OD-1 / OD-6 blocks
    is about, and their negative controls could not be admitted at all. Measured, not
    assumed: before this default existed, adding the G11 guard turned all four of those
    tests red.
    """
    market_root, market_rev = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "seed bars"},
        instrument_id=None,
    )
    market_rev.revision_state = MarketRevisionState.APPROVED
    if basis is not None:
        market_rev.record_time_basis = basis
    await session.flush()
    md_repo.add_processed_asset(
        session,
        entity_id=market_root.entity_id,
        object_key=f"market/processed/{market_root.entity_id}/seed.parquet",
        content_digest="seed-bars",
        size_bytes=4096,
        revision_id=market_rev.revision_id,
        row_count=22,
    )
    await session.flush()
    _reg, _pkg_root, pkg_rev = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"call": "ta.sma", "canonical_key": "ta.sma"}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=_strategy_payload(
            market_root.entity_id,
            market_rev.revision_id,
            market_rev.content_hash,
            indicator_revision_id=pkg_rev.revision_id,
            execution=execution,
        )
        | ({} if scaling is None else {"scaling_logic": scaling}),
    )
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()


async def _item_ids_by_kind(session, actor: Actor) -> dict[str, list[str]]:
    projection = await mb_query.get_default_mainboard(session, actor)
    out: dict[str, list[str]] = {}
    for item in projection["items"]:
        out.setdefault(str(item["item_kind"]), []).append(item["item_id"])
    return out


async def _enable_shared(session, composition_id: str, entries: list[dict[str, Any]]) -> None:
    await alloc_cmd.upsert_allocation_draft(
        session,
        USER1,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": "50000.00", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="0",
        entries=entries,
        idempotency_key="alloc-shared-mode-admission",
    )
    await session.commit()


async def _assert_nothing_admitted(session) -> None:
    """Doc 15 §9.3 — a refusal leaves no run, manifest, job or result behind.

    Jobs are counted on the ``backtest`` QUEUE rather than in total: the OD-6 setup
    drives the real Trade Log import pipeline, which legitimately owns an ``import``
    job committed long before admission was attempted. Counting every row would make
    this assertion fail for a reason that has nothing to do with the refusal — and,
    worse, would have to be loosened to a number, which would then pass even if a
    backtest job HAD been created.
    """
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, BacktestRunManifest) == 0
    assert await _count(session, BacktestResult) == 0
    queued_backtests = (
        await session.execute(select(func.count()).select_from(Job).where(Job.queue == "backtest"))
    ).scalar_one()
    assert queued_backtests == 0


# --------------------------------------------------------------------------- #
# OD-6(a) — a non-executing kind holding a sleeve                              #
# --------------------------------------------------------------------------- #


async def _two_strategy_composition(session, *, bases: tuple[Any, Any]) -> str:
    composition_id = await _empty_composition(session, USER1)
    for basis in bases:
        await _attach_ready_strategy(session, USER1, composition_id, basis=basis)
    return composition_id


async def test_od6_refuses_a_trade_log_holding_a_sleeve(
    session, monkeypatch, fake_object_store
) -> None:
    """A Trade Log the engine never simulates may not be given 40% of the pool."""
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)
    await _attach_ready_strategy(session, USER1, composition_id)
    await _attach_trade_log(session, USER1, composition_id)

    by_kind = await _item_ids_by_kind(session, USER1)
    await _enable_shared(
        session,
        composition_id,
        [
            {
                "composition_item_id": by_kind["strategy"][0],
                "active": True,
                "equity_share_percent": "60",
            },
            {
                "composition_item_id": by_kind["trade_log"][0],
                "active": True,
                "equity_share_percent": "40",
            },
        ],
    )

    with _lifted(monkeypatch), pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="od6-1"
        )
    await session.rollback()

    error = exc_info.value
    # Doc 14 §9.1 envelope, promoted by O-02: code + scope + field_path + remediation.
    assert error.code == "READINESS_BLOCKED"
    assert error.scope_type == "portfolio_allocation"
    assert error.field_path == "entries"
    assert error.remediation == NON_EXECUTING_ITEM_REMEDIATION
    detail = next(d for d in error.details if d["code"] == _OD6)
    assert detail["severity"] == "blocker"
    assert detail["message"] == NON_EXECUTING_ITEM_MESSAGE
    assert detail["scope_id"] == by_kind["trade_log"][0]
    await _assert_nothing_admitted(session)


async def test_od6_negative_control_a_strategy_only_plan_is_admitted(
    session, monkeypatch, fake_object_store
) -> None:
    """NEGATIVE CONTROL: the SAME composition, with the Trade Log entry deactivated.

    Only the offending fact differs, so a guard that refused everything — or that
    keyed off the Trade Log merely being in the composition rather than holding a
    sleeve — would fail here.
    """
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)
    await _attach_ready_strategy(session, USER1, composition_id)
    await _attach_trade_log(session, USER1, composition_id)

    by_kind = await _item_ids_by_kind(session, USER1)
    await _enable_shared(
        session,
        composition_id,
        [
            {
                "composition_item_id": by_kind["strategy"][0],
                "active": True,
                "equity_share_percent": "100",
            },
            {
                "composition_item_id": by_kind["trade_log"][0],
                "active": False,
                "equity_share_percent": "0",
            },
        ],
    )

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="od6-ok"
        )
    await session.commit()

    assert admit["state"] == "queued"
    assert await _count(session, BacktestRun) == 1


# --------------------------------------------------------------------------- #
# OD-1(a) — pinned revisions declaring different record time bases             #
# --------------------------------------------------------------------------- #


async def test_od1_refuses_two_differently_based_market_pins(session, monkeypatch) -> None:
    await _seed_principals(session)
    composition_id = await _two_strategy_composition(
        session, bases=(RecordTimeBasis.BAR_OPEN, RecordTimeBasis.BAR_CLOSE)
    )
    item_ids = (await _item_ids_by_kind(session, USER1))["strategy"]
    await _enable_shared(
        session,
        composition_id,
        [
            {"composition_item_id": item_ids[0], "active": True, "equity_share_percent": "50"},
            {"composition_item_id": item_ids[1], "active": True, "equity_share_percent": "50"},
        ],
    )

    with _lifted(monkeypatch), pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="od1-1"
        )
    await session.rollback()

    error = exc_info.value
    assert error.scope_type == "portfolio_allocation"
    assert error.field_path == "data.market_dataset_revision_id"
    assert error.remediation == MIXED_RECORD_TIME_BASIS_REMEDIATION
    detail = next(d for d in error.details if d["code"] == _OD1)
    # Cross-item defect: no single item is at fault, so no scope_id is claimed — but
    # the message must NAME the bases, or the reader cannot tell which pins disagree.
    assert detail["scope_id"] is None
    assert "bar_close, bar_open" in detail["message"]
    await _assert_nothing_admitted(session)


async def test_od1_negative_control_agreeing_bases_are_admitted(session, monkeypatch) -> None:
    """NEGATIVE CONTROL: two strategies, same basis — a legal shared composition."""
    await _seed_principals(session)
    composition_id = await _two_strategy_composition(
        session, bases=(RecordTimeBasis.BAR_CLOSE, RecordTimeBasis.BAR_CLOSE)
    )
    item_ids = (await _item_ids_by_kind(session, USER1))["strategy"]
    await _enable_shared(
        session,
        composition_id,
        [
            {"composition_item_id": item_ids[0], "active": True, "equity_share_percent": "50"},
            {"composition_item_id": item_ids[1], "active": True, "equity_share_percent": "50"},
        ],
    )

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="od1-ok"
        )
    await session.commit()

    assert admit["state"] == "queued"
    assert await _count(session, BacktestRun) == 1


# --------------------------------------------------------------------------- #
# The shipped world is unchanged                                               #
# --------------------------------------------------------------------------- #


async def test_containment_still_leads_in_the_shipped_world(session, monkeypatch) -> None:
    """Unlifted, a violating composition is refused by CONTAINMENT, not by OD-1/OD-6.

    The two new guards sit behind the containment guard on purpose. If a later edit
    moved either of them in front, this test would report the new code and go red —
    which is the point: containment is the sharper statement while the flag is off.
    """
    # CONTAINED WORLD, forced since ADIM 20 (`C9`). This case characterizes the
    # containment blanket, which the lift removed as the shipped default but did not
    # delete: `future_dev` is still a legal status and still behaves exactly this way.
    monkeypatch.setattr(capability, "SHARED_ALLOCATION_STATUS", "future_dev")
    await _seed_principals(session)
    composition_id = await _two_strategy_composition(
        session, bases=(RecordTimeBasis.BAR_OPEN, RecordTimeBasis.BAR_CLOSE)
    )
    item_ids = (await _item_ids_by_kind(session, USER1))["strategy"]
    await _enable_shared(
        session,
        composition_id,
        [
            {"composition_item_id": item_ids[0], "active": True, "equity_share_percent": "50"},
            {"composition_item_id": item_ids[1], "active": True, "equity_share_percent": "50"},
        ],
    )

    with pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="shipped-1"
        )
    await session.rollback()

    codes = {d["code"] for d in exc_info.value.details}
    assert _CONTAINMENT in codes
    assert _OD1 not in codes and _OD6 not in codes
    await _assert_nothing_admitted(session)


# --------------------------------------------------------------------------- #
# G11 (P2 — deferred / resting fills) and G12 (P8 — scaling)                   #
# --------------------------------------------------------------------------- #


async def _one_strategy_shared(session, **strategy: Any) -> str:
    """A single-Strategy composition with an ENABLED shared plan taking the whole pool."""
    composition_id = await _empty_composition(session, USER1)
    await _attach_ready_strategy(session, USER1, composition_id, **strategy)
    item_ids = (await _item_ids_by_kind(session, USER1))["strategy"]
    await _enable_shared(
        session,
        composition_id,
        [{"composition_item_id": item_ids[0], "active": True, "equity_share_percent": "100"}],
    )
    return composition_id


async def test_g11_refuses_a_deferring_entry_timing(session, monkeypatch) -> None:
    """G11 §Karar disposition (a). The refusal reaches the caller through Ready Check's
    preflight, which is the surface the signature's "ikisi de" asks for first."""
    await _seed_principals(session)
    composition_id = await _one_strategy_shared(
        session,
        execution={"entry_timing": "next_candle_open", "exit_timing": "current_candle_close"},
    )

    with _lifted(monkeypatch), pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="g11-1"
        )
    await session.rollback()

    error = exc_info.value
    assert error.scope_type == "portfolio_allocation"
    # O-02: the leader names the SETTING to change, not the toggle — a user with one
    # offending Strategy fixes the Strategy.
    assert error.field_path == "data.execution.entry_timing"
    assert error.remediation == DEFERRED_FILL_REMEDIATION
    paths = [d["field"] for d in error.details if d["code"] == _G11]
    # ... and the toggle is still IN the list: "ikisi de".
    assert paths == ["data.execution.entry_timing", "enabled"]
    await _assert_nothing_admitted(session)


async def test_ready_check_itself_reports_both_gates_on_the_page(session, monkeypatch) -> None:
    """The READY CHECK half of "ikisi de", proved on its own surface.

    Measured, not assumed: with the admission guard in place, silencing the Ready Check
    side leaves every other test in this file GREEN — admission catches the run either
    way (negative control NC-3). So an assertion that only drives ``request_backtest_run``
    proves the pair, never the half. This one reads the persisted report instead, which
    is what the Portfolio / Ready Check page renders.
    """
    await _seed_principals(session)
    composition_id = await _one_strategy_shared(
        session,
        execution={"entry_timing": "next_candle_open", "exit_timing": "current_candle_close"},
        scaling=_SCALING_ON,
    )

    with _lifted(monkeypatch):
        report = await readiness_cmd.run_readiness_check(
            session, USER1, composition_id=composition_id
        )
    await session.commit()

    assert report["state"] == "not_ready"
    blockers = [i for i in report["issues"] if i["severity"] == "blocker"]
    assert {_G11, _G12} <= {i["code"] for i in blockers}
    g11 = next(i for i in blockers if i["code"] == _G11)
    # doc 14 §9.1 — a blocker is a code AND an actionable remediation AND a field.
    assert g11["remediation"] == DEFERRED_FILL_REMEDIATION
    assert g11["field_path"] == "data.execution.entry_timing"
    assert g11["scope_id"] is not None


async def test_g12_refuses_enabled_scaling(session, monkeypatch) -> None:
    """G12 §Karar 6 option A. Its own code, so the page can say WHICH gate refused."""
    await _seed_principals(session)
    composition_id = await _one_strategy_shared(session, scaling=_SCALING_ON)

    with _lifted(monkeypatch), pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="g12-1"
        )
    await session.rollback()

    error = exc_info.value
    assert error.field_path == "scaling_logic.enabled"
    assert error.remediation == SCALING_REMEDIATION
    blockers = {d["code"] for d in error.details if d["severity"] == "blocker"}
    assert blockers == {_G12}
    await _assert_nothing_admitted(session)


async def test_g11_g12_negative_control_an_immediate_unscaled_strategy_is_admitted(
    session, monkeypatch
) -> None:
    """NEGATIVE CONTROL: the same composition, differing only in the offending fields.

    A guard that refused every shared run — or that keyed off the plan being enabled
    rather than the Strategy's shape — would fail here."""
    await _seed_principals(session)
    composition_id = await _one_strategy_shared(session)

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="g11-ok"
        )
    await session.commit()

    assert admit["state"] == "queued"
    assert await _count(session, BacktestRun) == 1


async def test_the_admission_guard_holds_when_ready_check_is_bypassed(session, monkeypatch) -> None:
    """The 3d guard does not depend on the readiness evaluation producing the finding.

    A regressed / replaced / short-circuited allocation resolution is simulated by making
    the readiness command report the plan as INDEPENDENT while the pinned capital
    snapshot still asks for shared capital. Ready Check then emits no shape blocker at
    all — and admission must STILL refuse, because it reads the snapshot and the configs
    the manifest is about to pin, not the report.
    """
    await _seed_principals(session)
    composition_id = await _one_strategy_shared(
        session,
        execution={"entry_timing": "next_candle_open", "exit_timing": "current_candle_close"},
    )

    real_resolve = readiness_cmd._resolve_allocation

    async def _blind_resolve(*args: Any, **kwargs: Any):
        _enabled, _issues, capital_mode = await real_resolve(*args, **kwargs)
        return False, [], capital_mode  # reported independent; the SNAPSHOT still says shared

    monkeypatch.setattr(readiness_cmd, "_resolve_allocation", _blind_resolve)

    with _lifted(monkeypatch):
        # The preflight really is clean — proving the bypass is effective, not merely
        # attempted. Without this the test could pass on a report that still blocked.
        report = await readiness_cmd.run_readiness_check(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        assert report["summary"]["blocker_count"] == 0

        with pytest.raises(ReadinessBlockedError) as exc_info:
            await backtest_cmd.request_backtest_run(
                session, USER1, composition_id=composition_id, idempotency_key="g11-bypass"
            )
    await session.rollback()

    blockers = {d["code"] for d in exc_info.value.details if d["severity"] == "blocker"}
    assert blockers == {_G11}
    await _assert_nothing_admitted(session)


async def test_containment_still_leads_for_a_g11_violation_in_the_shipped_world(
    session, monkeypatch
) -> None:
    """SHIPPED WORLD. Unlifted, the one finding is containment — shared mode is not
    unavailable *for this Strategy*, it is unavailable at all, and three more blockers
    behind that one would bury the actionable message."""
    # CONTAINED WORLD, forced since ADIM 20 (`C9`). This case characterizes the
    # containment blanket, which the lift removed as the shipped default but did not
    # delete: `future_dev` is still a legal status and still behaves exactly this way.
    monkeypatch.setattr(capability, "SHARED_ALLOCATION_STATUS", "future_dev")
    await _seed_principals(session)
    composition_id = await _one_strategy_shared(
        session,
        execution={"entry_timing": "next_candle_open", "exit_timing": "current_candle_close"},
    )

    with pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="g11-shipped"
        )
    await session.rollback()

    codes = {d["code"] for d in exc_info.value.details}
    assert _CONTAINMENT in codes
    assert _G11 not in codes and _G12 not in codes
    await _assert_nothing_admitted(session)


async def test_independent_mode_still_admits_the_very_same_strategy(session) -> None:
    """G11's closing-constraint 4, explicitly required by the signature: the block must close
    what it names and nothing else.

    The identical Strategy — deferring entry timing AND enabled scaling — is admitted
    with no allocation plan. Independent mode replays it against its own ledger, where
    P2 and P8 are both fully modelled (doc 13 §1.1: a complete mode, not a degraded one).
    If this ever goes red the gate has leaked out of shared capital."""
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)
    await _attach_ready_strategy(
        session,
        USER1,
        composition_id,
        execution={"entry_timing": "next_candle_open", "exit_timing": "next_candle_open"},
        scaling=_SCALING_ON,
    )

    admit = await backtest_cmd.request_backtest_run(
        session, USER1, composition_id=composition_id, idempotency_key="independent-ok"
    )
    await session.commit()

    assert admit["state"] == "queued"
    assert await _count(session, BacktestRun) == 1
