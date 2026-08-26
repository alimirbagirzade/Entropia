"""ADIM 19 — the unified-clock portfolio manifest section (contained).

Canon under test: doc 13 §13 — a shared-mode run manifest must carry the exact
``portfolio_allocation_plan_revision_id``, the resolved sleeve amounts, the currency/FX
refs, the compounding mode and the allocation engine policy version — together with
Modül 11 §10 (the literal ``backtest_run_manifest.portfolio_allocation`` shape) and
ADR 0002 §10.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.rules import (
    AllocationItemRef,
    validate_allocation,
)
from entropia.domain.backtest.artifacts import ArtifactType, compute_artifact_checksum
from entropia.domain.backtest.execution.arbitration import (
    ARBITRATION_POLICY_VERSION,
    resolve_policy,
)
from entropia.domain.backtest.execution.attribution import (
    ATTRIBUTION_POLICY_VERSION,
    CONTRIBUTION_METHOD,
)
from entropia.domain.backtest.execution.clock import CLOCK_POLICY_VERSION
from entropia.domain.backtest.execution.intents import INTENT_CONTRACT_VERSION, ItemIdentity
from entropia.domain.backtest.execution.portfolio_ledger import (
    LEDGER_POLICY_VERSION,
    PortfolioEquityPoint,
    build_sleeve_plan,
)
from entropia.domain.backtest.execution.provenance import (
    ENGINE_ALLOCATION_POLICY_VERSION,
    MARK_STALENESS_POLICY,
    MARK_STALENESS_STATUS,
    PORTFOLIO_MANIFEST_VERSION,
    SLEEVE_AMOUNT_DIVERGENCE,
    DuplicatePinOrdinalError,
    MissingAllocationProvenanceError,
    UnknownProvenanceItemError,
    allocation_provenance_from_derived,
    build_portfolio_manifest,
    independent_allocation_provenance,
    ledger_artifact_ref,
    ledger_equity_rows,
    pinned_items_from_identities,
    sleeve_amount_divergences,
)

_ENGINE = "backtest-engine-test"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _config(capital: str, reserve: str, shares: dict[str, str]) -> PortfolioAllocationConfigV1:
    return PortfolioAllocationConfigV1.model_validate(
        {
            "enabled": True,
            "initial_capital": {"amount": capital, "currency": "USDT"},
            "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
            "reserve_cash_percent": reserve,
            "entries": [
                {
                    "composition_item_id": item,
                    "item_type": "STRATEGY",
                    "active": True,
                    "equity_share_percent": share,
                }
                for item, share in shares.items()
            ],
        }
    )


def _derived(config: PortfolioAllocationConfigV1) -> dict[str, object]:
    refs = {
        entry.composition_item_id: AllocationItemRef(
            kind=entry.item_type, available=True, settlement_currency="USDT"
        )
        for entry in config.entries
    }
    _issues, derived = validate_allocation(config, item_refs=refs)
    assert derived is not None
    return derived.as_dict()


def _identities() -> list[ItemIdentity]:
    return [
        ItemIdentity(
            item_id="ci_a",
            item_kind="strategy",
            pin_ordinal=0,
            root_id="root_a",
            selected_revision_id="rev_a",
            item_label="Momentum",
        ),
        ItemIdentity(
            item_id="ci_b",
            item_kind="strategy",
            pin_ordinal=1,
            root_id="root_b",
            selected_revision_id="rev_b",
            item_label="Mean reversion",
        ),
    ]


def _allocation(shares: dict[str, str] | None = None):
    config = _config("10000.00", "10.00", shares or {"ci_a": "40.00", "ci_b": "35.00"})
    return allocation_provenance_from_derived(
        _derived(config),
        plan_id="pal_1",
        plan_revision_id="palr_1",
        config_hash="cfg_hash",
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        item_revision_ids={"ci_a": "rev_a", "ci_b": "rev_b"},
        fx_refs=(),
    )


def _points() -> list[PortfolioEquityPoint]:
    return [
        PortfolioEquityPoint(
            seq=0,
            t_ms=None,
            equity=Decimal("10000.00"),
            drawdown=Decimal("0.00"),
            gross_exposure_percent=Decimal("0.00"),
        ),
        PortfolioEquityPoint(
            seq=1,
            t_ms=1_000,
            equity=Decimal("10490.00"),
            drawdown=Decimal("0.00"),
            gross_exposure_percent=Decimal("0.00"),
        ),
    ]


def _manifest(**overrides):
    kwargs: dict[str, object] = {
        "engine_version": _ENGINE,
        "allocation": _allocation(),
        "identities": _identities(),
        "conflict_policy": resolve_policy(None),
        "tick_instants": [1_000, 2_000, 3_000],
        "equity_points": _points(),
    }
    kwargs.update(overrides)
    return build_portfolio_manifest(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 1. resolved sleeve amounts — parity with the SHIPPED preview
# --------------------------------------------------------------------------- #
def test_doc13_test10_sleeve_amounts_match_the_shipped_preview_exactly() -> None:
    """doc 13 §14 test 10: 10,000 / reserve 10 % / 40-35-15 -> R0=1,000, A0=9,000,
    sleeves 3,600/3,150/1,350, unallocated 900.

    The parity is PROVEN by calling ``validate_allocation`` — the shipped preview path —
    rather than restating its arithmetic here."""
    config = _config("10000.00", "10.00", {"ci_a": "40.00", "ci_b": "35.00", "ci_c": "15.00"})
    allocation = allocation_provenance_from_derived(
        _derived(config),
        plan_id="pal_1",
        plan_revision_id="palr_1",
        config_hash="cfg_hash",
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
    )
    assert allocation.initial_capital == "10000.00"
    assert allocation.reserve_amount == "1000.00"
    assert allocation.capital_available == "9000.00"
    assert allocation.total_allocated == "8100.00"
    assert allocation.unallocated == "900.00"
    assert allocation.active_share_total == "90.00"
    assert [entry.initial_sleeve_capital for entry in allocation.entries] == [
        "3600.00",
        "3150.00",
        "1350.00",
    ]

    plan = build_sleeve_plan(
        pool_initial=Decimal("10000.00"),
        reserve_percent=Decimal("10.00"),
        shares={"ci_a": Decimal("40.00"), "ci_b": Decimal("35.00"), "ci_c": Decimal("15.00")},
        compound=True,
    )
    assert plan.reserve_nominal == Decimal("1000.00")
    assert plan.allocatable_initial == Decimal("9000.00")
    assert plan.unallocated_initial == Decimal("900.00")
    assert sleeve_amount_divergences(allocation, plan) == ()


def test_the_half_cent_tie_divergence_is_reported_not_silently_resolved() -> None:
    """``allocation.rules._money`` is ROUND_HALF_UP; the ledger money step is
    ROUND_HALF_EVEN. At 1,000.10 * 25 % = 250.025 they disagree by one cent. doc 13 §13
    forbids a preview/manifest mismatch and no canon rule picks a winner, so the manifest
    keeps the frozen preview number and SURFACES the divergence."""
    config = _config("1000.10", "0.00", {"ci_a": "50.00", "ci_b": "25.00"})
    allocation = allocation_provenance_from_derived(
        _derived(config),
        plan_id="pal_1",
        plan_revision_id="palr_1",
        config_hash="cfg_hash",
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
    )
    plan = build_sleeve_plan(
        pool_initial=Decimal("1000.10"),
        reserve_percent=Decimal("0.00"),
        shares={"ci_a": Decimal("50.00"), "ci_b": Decimal("25.00")},
        compound=True,
    )
    findings = sleeve_amount_divergences(allocation, plan)
    assert [f["composition_item_snapshot_id"] for f in findings] == ["ci_b"]
    assert findings[0]["code"] == SLEEVE_AMOUNT_DIVERGENCE
    assert findings[0]["manifest_initial_sleeve_capital"] == "250.03"
    assert findings[0]["executed_sleeve_capital"] == "250.02"
    assert findings[0]["executed_sleeve_capital_exact"] == "250.025000"
    # the manifest still carries the FROZEN preview amount, unchanged
    assert allocation.entries[1].initial_sleeve_capital == "250.03"


def test_an_allocation_entry_with_no_executed_sleeve_is_refused() -> None:
    allocation = _allocation()
    plan = build_sleeve_plan(
        pool_initial=Decimal("10000.00"),
        reserve_percent=Decimal("10.00"),
        shares={"ci_a": Decimal("40.00")},
        compound=True,
    )
    with pytest.raises(UnknownProvenanceItemError):
        sleeve_amount_divergences(allocation, plan)


# --------------------------------------------------------------------------- #
# 2. canonical field names (Modül 11 §10 literal)
# --------------------------------------------------------------------------- #
def test_the_allocation_block_uses_canon_field_names_verbatim() -> None:
    payload = _allocation().as_dict()
    assert set(payload) == {
        "enabled",
        "plan_id",
        "plan_revision_id",
        "config_hash",
        "base_currency",
        "compounding_mode",
        "initial_capital",
        "reserve_amount",
        "capital_available",
        "total_allocated",
        "unallocated",
        "active_share_total",
        "entries",
        "fx_refs",
        "engine_allocation_policy_version",
    }
    assert payload["engine_allocation_policy_version"] == "portfolio-allocation-v1"
    assert set(payload["entries"][0]) == {
        "composition_item_snapshot_id",
        "item_revision_id",
        "share_percent",
        "initial_sleeve_capital",
    }


def test_independent_mode_states_enabled_false_explicitly() -> None:
    """doc 13 §13: the revision id may be null, but ``enabled=false`` must be explicit."""
    payload = independent_allocation_provenance().as_dict()
    assert payload["enabled"] is False
    assert payload["plan_revision_id"] is None
    assert payload["engine_allocation_policy_version"] == ENGINE_ALLOCATION_POLICY_VERSION


def test_a_shared_manifest_without_the_frozen_record_is_refused() -> None:
    shared = replace(independent_allocation_provenance(), enabled=True)
    with pytest.raises(MissingAllocationProvenanceError):
        _manifest(allocation=shared)


# --------------------------------------------------------------------------- #
# 3. policy versions are pinned
# --------------------------------------------------------------------------- #
def test_every_policy_knob_is_pinned_in_the_manifest() -> None:
    versions = _manifest().policy_versions()
    assert versions["portfolio_manifest_version"] == PORTFOLIO_MANIFEST_VERSION
    assert versions["engine_version"] == _ENGINE
    assert versions["clock_policy_version"] == CLOCK_POLICY_VERSION
    assert versions["intent_contract_version"] == INTENT_CONTRACT_VERSION
    assert versions["portfolio_ledger_policy_version"] == LEDGER_POLICY_VERSION
    assert versions["arbitration_policy_version"] == ARBITRATION_POLICY_VERSION
    assert versions["attribution_policy_version"] == ATTRIBUTION_POLICY_VERSION
    assert versions["engine_allocation_policy_version"] == ENGINE_ALLOCATION_POLICY_VERSION
    assert versions["contribution_method"] == CONTRIBUTION_METHOD
    assert versions["money_quantum"] == "0.01"
    assert versions["quantity_quantum"] == "1E-8"
    assert versions["money_rounding"] == "ROUND_HALF_EVEN"


def test_the_open_mark_staleness_decision_is_disclosed_not_defaulted() -> None:
    """ADR 0002 §13 OD-2 is unanswered. The manifest must say so, not pick a policy."""
    versions = _manifest().policy_versions()
    assert versions["mark_staleness_policy"] == MARK_STALENESS_POLICY == "undefined_pending_od2"
    assert versions["mark_staleness_status"] == MARK_STALENESS_STATUS == "open_decision"
    assert "OD-2" in versions["mark_staleness_tracking"]


# --------------------------------------------------------------------------- #
# 4. determinism + tamper-evidence
# --------------------------------------------------------------------------- #
def test_the_manifest_identity_is_deterministic() -> None:
    assert _manifest().identity == _manifest().identity
    assert len(_manifest().identity) == 64


def test_the_manifest_identity_ignores_display_labels() -> None:
    """A rename must never fork reproducibility identity — the same split
    ``manifest.pinned_item_labels`` makes for the sequential manifest."""
    renamed = [
        ItemIdentity(
            item_id=i.item_id,
            item_kind=i.item_kind,
            pin_ordinal=i.pin_ordinal,
            root_id=i.root_id,
            selected_revision_id=i.selected_revision_id,
            item_label=f"RENAMED {i.item_label}",
        )
        for i in _identities()
    ]
    base = _manifest()
    after = _manifest(identities=renamed)
    assert after.identity == base.identity
    assert (
        after.as_dict()["presentation"]["item_labels"]
        != (base.as_dict()["presentation"]["item_labels"])
    )
    assert "RENAMED" not in str(after.execution_content())


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"engine_version": "other-engine"}, id="engine_version"),
        pytest.param({"tick_instants": [1_000, 2_000]}, id="timeline"),
        pytest.param({"equity_points": _points()[:1]}, id="ledger_artifact"),
        pytest.param({"allocation": _allocation({"ci_a": "41.00", "ci_b": "35.00"})}, id="sleeves"),
    ],
)
def test_the_manifest_identity_is_tamper_evident(overrides: dict[str, object]) -> None:
    assert _manifest(**overrides).identity != _manifest().identity


def test_a_changed_pinned_revision_changes_the_identity() -> None:
    swapped = [
        ItemIdentity(
            item_id=i.item_id,
            item_kind=i.item_kind,
            pin_ordinal=i.pin_ordinal,
            root_id=i.root_id,
            selected_revision_id="rev_TAMPERED" if i.item_id == "ci_a" else i.selected_revision_id,
            item_label=i.item_label,
        )
        for i in _identities()
    ]
    assert _manifest(identities=swapped).identity != _manifest().identity


def test_the_item_order_recorded_is_the_merge_order() -> None:
    reversed_input = list(reversed(_identities()))
    items = pinned_items_from_identities(reversed_input)
    assert [item.item_id for item in items] == ["ci_a", "ci_b"]
    assert [item.pin_ordinal for item in items] == [0, 1]
    # feeding the same set in a different input order yields the same identity
    assert _manifest(identities=reversed_input).identity == _manifest().identity


def test_a_duplicate_pin_ordinal_is_refused() -> None:
    clashing = [
        ItemIdentity(item_id="ci_a", item_kind="strategy", pin_ordinal=0),
        ItemIdentity(item_id="ci_b", item_kind="strategy", pin_ordinal=0),
    ]
    with pytest.raises(DuplicatePinOrdinalError):
        pinned_items_from_identities(clashing)


def test_data_revisions_are_pinned_per_item() -> None:
    manifest = _manifest(
        data_revisions={"ci_a": {"market_dataset_revision_id": "mdr_1"}},
    )
    items = {item.item_id: item for item in manifest.items}
    assert items["ci_a"].data_revisions == {"market_dataset_revision_id": "mdr_1"}
    assert items["ci_b"].data_revisions == {}
    moved = _manifest(data_revisions={"ci_a": {"market_dataset_revision_id": "mdr_2"}})
    assert moved.identity != manifest.identity


# --------------------------------------------------------------------------- #
# 5. ledger artifact reference + checksum
# --------------------------------------------------------------------------- #
def test_the_ledger_artifact_checksum_is_the_shipped_artifact_checksum() -> None:
    """Reuse, not a second hashing scheme: the expectation is produced by calling the
    shipped ``compute_artifact_checksum`` rather than by restating a digest literal."""
    points = _points()
    ref = ledger_artifact_ref(points)
    assert ref.artifact_type == str(ArtifactType.EQUITY_CURVE)
    assert ref.row_count == 2
    assert ref.checksum == compute_artifact_checksum(
        ArtifactType.EQUITY_CURVE, ledger_equity_rows(points)
    )
    assert ref.schema_version == "artifact-checksum-v1"


def test_the_ledger_artifact_checksum_detects_a_mutated_equity_point() -> None:
    points = _points()
    tampered = [
        points[0],
        PortfolioEquityPoint(
            seq=1,
            t_ms=1_000,
            equity=Decimal("10490.01"),
            drawdown=Decimal("0.00"),
            gross_exposure_percent=Decimal("0.00"),
        ),
    ]
    assert ledger_artifact_ref(tampered).checksum != ledger_artifact_ref(points).checksum


def test_the_seed_point_is_part_of_the_checksummed_series() -> None:
    """A series that gains a seed point must not collide with one that never had it."""
    points = _points()
    assert ledger_artifact_ref(points[1:]).checksum != ledger_artifact_ref(points).checksum
    assert ledger_equity_rows(points)[0]["t_ms"] is None


def test_a_run_with_no_equity_points_carries_no_fabricated_artifact_ref() -> None:
    assert _manifest(equity_points=[]).ledger_artifact is None


# --------------------------------------------------------------------------- #
# 6. conflict policy + time alignment are recorded
# --------------------------------------------------------------------------- #
def test_the_conflict_policy_and_time_alignment_are_recorded() -> None:
    content = _manifest().execution_content()
    assert content["conflict_policy"]["policy"] == "KEEP_SEPARATE"
    assert content["conflict_policy"]["supported"] is True
    assert content["conflict_policy"]["selection_policy"] == "pin_order_admission"
    assert content["conflict_policy"]["selection_status"] == "recommended_pending_approval"
    assert content["time_alignment"]["tick_count"] == 3
    assert content["time_alignment"]["first_t_ms"] == 1_000
    assert content["time_alignment"]["last_t_ms"] == 3_000
    assert len(content["time_alignment"]["timeline_identity"]) == 64


def test_duplicate_tick_instants_do_not_change_the_axis() -> None:
    assert _manifest(tick_instants=[3_000, 1_000, 2_000, 1_000]).identity == _manifest().identity


# --------------------------------------------------------------------------- #
# 7. containment
# --------------------------------------------------------------------------- #
def _imports_provenance(source: str) -> bool:
    return (
        "execution.provenance" in source
        or "execution import provenance" in source
        or "from . import provenance" in source
    )


#: The production modules that may name the provenance layer, as an EXHAUSTIVE list.
#: Narrowed from ``== []`` at 27C, never deleted: the layer gained a production caller, so
#: "nobody imports it" stopped being true, but "anybody may import it" was never the
#: replacement. ``portfolio_projection.py`` is the seam — it sits INSIDE ``execution/``
#: precisely so the worker can reach the section without naming the phase loop's vocabulary,
#: which would widen the SIGNED importer allowlist that
#: ``oracles/test_oracle_portfolio_containment_gate.py`` holds at two named modules.
_AUTHORISED_PROVENANCE_IMPORTERS = ["domain/backtest/execution/portfolio_projection.py"]


def test_the_provenance_layer_has_exactly_one_production_importer() -> None:
    """27C wired the manifest section; this bounds WHERE it may be assembled from.

    Was ``test_nothing_in_production_imports_the_provenance_layer_yet``, asserting ``== []``.
    That assertion was correct while ``build_portfolio_manifest`` had no production caller
    and the ``unified_clock`` branch of ``portfolio_mode`` was unreachable from any real
    Result. Both changed here, so the assertion is re-aimed rather than relaxed: a SECOND
    importer — a route, a command, the worker itself — is still a red build.
    """
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = sorted(
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "provenance.py" and _imports_provenance(path.read_text(encoding="utf-8"))
    )
    assert importers == _AUTHORISED_PROVENANCE_IMPORTERS, (
        f"the provenance layer gained an unauthorised production importer: {importers}"
    )


def test_both_unified_clock_entry_points_have_a_production_caller() -> None:
    """27C's acceptance criterion, stated directly.

    ``project_portfolio_run`` gained one at `C4`; ``build_portfolio_manifest`` had none at
    all, which is why the ``unified_clock`` branch of ``portfolio_mode`` was unreachable from
    any real Result. Asserted as *some production module outside this layer calls it*, which
    is the weakest form of the claim — the behavioural proof that the call actually happens
    on a live run is ``tests/integration/test_unified_portfolio_provenance.py``, and the
    bound on WHERE it may be called from is the allowlist above."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    sources = {
        path.relative_to(src).as_posix(): path.read_text(encoding="utf-8")
        for path in src.rglob("*.py")
    }
    for symbol, definer in (
        ("build_portfolio_manifest", "domain/backtest/execution/provenance.py"),
        ("project_portfolio_run", "domain/backtest/execution/portfolio_projection.py"),
    ):
        callers = sorted(
            path for path, text in sources.items() if path != definer and f"{symbol}(" in text
        )
        assert callers, f"{symbol} still has no production caller"


def test_the_worker_reaches_provenance_through_the_seam_and_not_by_importing_it() -> None:
    """The worker CALLS the section builder and never names the provenance layer.

    This is the half the allowlist above cannot state. That list would stay satisfied if the
    worker stopped building a section at all, so it proves nothing about the wiring being
    live; and the containment gate's own scan is blind here because it exempts everything
    inside ``execution/``. Together: the worker calls the seam (so the section is really
    assembled in production) AND does not import the layer (so the signed allowlist that
    gate holds is untouched)."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    worker = (src / "application" / "jobs" / "backtest_engine.py").read_text(encoding="utf-8")
    assert "build_portfolio_provenance(" in worker
    assert not _imports_provenance(worker)


def test_no_portfolio_manifest_field_ships_in_the_shipped_manifest_yet() -> None:
    """The shipped sequential manifest must stay untouched: this slice adds the CONTRACT,
    not the wiring. Lifting containment is ADIM 20's job (ADR 0002 §12)."""
    shipped = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "entropia"
        / "domain"
        / "backtest"
        / "manifest.py"
    ).read_text(encoding="utf-8")
    for field in (
        "portfolio_manifest_version",
        "engine_allocation_policy_version",
        "clock_policy_version",
        "arbitration_policy_version",
        "attribution_policy_version",
        "mark_staleness_policy",
        "portfolio-allocation-v1",
        "portfolio-manifest-v1",
    ):
        assert field not in shipped, f"{field!r} leaked into the shipped manifest"
    # The literal tracks whatever the CURRENT shipped version is; #550/#551/#552 moved it.
    # What the assertion pins is that lifting containment cannot happen without editing
    # this line, not the particular string.
    assert 'ENGINE_VERSION = "backtest-engine-v18-percent-sizing-per-fill-commission"' in shipped
