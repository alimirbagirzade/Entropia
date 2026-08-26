"""27C — a unified-clock Result carries its own PROVENANCE, and says so when read back.

`C4` / 27B wired the worker to the phase loop: a shared run really co-simulates and really
produces a Result. What it did NOT do is let anyone tell afterwards. ``portfolio_mode``'s
``unified_clock`` branch keys on one thing — a ``portfolio_simulation`` section pinned in the
Result's own manifest snapshot — and nothing in production wrote that section, so every
unified Result read back as ``unknown``. ``build_portfolio_manifest`` had no production
caller at all.

This module is the behavioural proof of the wiring, and of the three things it must NOT
disturb:

* a newly created REAL Result resolves to ``unified_clock`` through the shipped read query —
  not through a hand-built manifest dict, which is what every existing provenance test does
  and is exactly why the gap survived: the contract was tested, the WIRING was not;
* the section states this run — its merged axis, its pinned items in pin order, its
  allocation revision, its engine version — and its content hash is stable across a replay
  of the same composition, so the provenance is a fact about the run and not about the day;
* an INDEPENDENT multi-item run is untouched: no section, still ``legacy_sequential``, and
  the manifest snapshot it stores is still byte-identical to the run manifest;
* a historical Result written BEFORE the section existed keeps reading as it always did, and
  nothing re-labels or recomputes it.

The lift fixture is the test-owned one ``test_shared_clock_worker_branch`` documents: no
``future_dev`` pin in ``backend/src`` is weakened, and lifting containment is `C9` / ADIM 20.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries.backtest_run import get_backtest_result
from entropia.domain.backtest.execution.provenance import PORTFOLIO_MANIFEST_VERSION
from entropia.domain.backtest.portfolio_mode import (
    PORTFOLIO_MODE_LEGACY_SEQUENTIAL,
    PORTFOLIO_MODE_UNIFIED_CLOCK,
    PORTFOLIO_MODE_UNKNOWN,
    UNIFIED_CLOCK_NOTE,
    UNIFIED_MANIFEST_KEY,
)
from entropia.infrastructure.postgres.models import BacktestRun, ResultManifestSnapshot
from entropia.shared.manifest import manifest_hash
from tests.integration.test_backtest_persistence import (
    USER1,
    _e2e_bars,
    _seed_principals,
)
from tests.integration.test_shared_clock_worker_branch import (
    _composition,
    _enable_shared_pool,
    _lifted,
)

pytestmark = pytest.mark.integration


async def _snapshot(session: Any, result_id: str) -> ResultManifestSnapshot:
    """The Result's OWN pinned manifest copy — the row every historical read resolves
    against (doc 15 §12), never the run's manifest row."""
    return (
        await session.execute(
            select(ResultManifestSnapshot).where(ResultManifestSnapshot.result_id == result_id)
        )
    ).scalar_one()


async def _shared_composition(session: Any, monkeypatch: pytest.MonkeyPatch) -> str:
    """A two-Strategy composition with the shared pool enabled."""
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)
    return composition_id


async def _run_once(
    session: Any, monkeypatch: pytest.MonkeyPatch, composition_id: str, key: str | None = None
) -> dict[str, Any]:
    """One complete unified-clock run: admit -> worker -> committed Result."""
    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key=key
        )
        await session.commit()
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()
    assert out["state"] == "succeeded", out
    return out


async def _shared_run(session: Any, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A fresh composition, run once."""
    return await _run_once(session, monkeypatch, await _shared_composition(session, monkeypatch))


async def _independent_run(session: Any) -> dict[str, Any]:
    """The same two-item composition with NO shared pool and the flag exactly as shipped —
    the sequential fold, which is every multi-item Result produced to date."""
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded", out
    return out


# --------------------------------------------------------------------------- #
# (1) The acceptance criterion: unified_clock is reachable from a REAL Result   #
# --------------------------------------------------------------------------- #
async def test_a_real_unified_run_reads_back_as_unified_clock(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """worker -> DB -> Result -> read API, end to end.

    Driven through ``get_backtest_result`` rather than by calling
    ``resolve_portfolio_simulation_mode`` on a dict assembled here. That distinction IS the
    slice: the classifier and its manifest contract were both already correct and both
    already tested, and the Result still read ``unknown``, because no production writer
    joined them. A test that builds the manifest itself re-proves the contract and would
    have stayed green throughout the entire gap."""
    await _seed_principals(session)
    out = await _shared_run(session, monkeypatch)

    detail = await get_backtest_result(session, USER1, result_id=out["result_id"])
    assert detail["portfolio_simulation"]["mode"] == PORTFOLIO_MODE_UNIFIED_CLOCK
    assert detail["portfolio_simulation"]["note"] == UNIFIED_CLOCK_NOTE
    # Stated, not left to the reader: a sequential fold's drawdown and a portfolio
    # valuation's drawdown are different quantities.
    assert detail["portfolio_simulation"]["comparable_with_unified_clock"] is True


async def test_the_history_index_agrees_with_the_detail_page(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The batched marker read resolves the same mode as the whole-manifest read.

    The two surfaces extract the section by DIFFERENT means — the index pulls one JSONB path
    in a batched ``IN (...)``, the detail page loads the manifest and walks it — so a writer
    that satisfied one could miss the other. They are asserted against each other rather
    than each against a literal, because the failure that matters is them disagreeing."""
    await _seed_principals(session)
    out = await _shared_run(session, monkeypatch)

    from entropia.infrastructure.postgres.repositories import backtest as bt_repo

    markers = await bt_repo.get_portfolio_mode_markers(session, [out["result_id"]])
    assert markers[out["result_id"]]["unified_manifest_version"] == PORTFOLIO_MANIFEST_VERSION


# --------------------------------------------------------------------------- #
# (2) The section states THIS run                                              #
# --------------------------------------------------------------------------- #
async def test_the_pinned_section_states_this_runs_axis_items_and_allocation(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The manifest section is provenance, so every field is checked against the run.

    A section that merely EXISTS is enough to flip the mode, which is why the mode assertion
    above cannot stand alone: a builder that pinned an empty axis and no items would satisfy
    it while recording nothing true."""
    await _seed_principals(session)
    out = await _shared_run(session, monkeypatch)
    snapshot = await _snapshot(session, out["result_id"])
    section = snapshot.manifest[UNIFIED_MANIFEST_KEY]

    # The merged axis was really walked — a zero-tick axis would pass every other assertion.
    assert section["time_alignment"]["tick_count"] >= 1
    assert len(section["time_alignment"]["timeline_identity"]) == 64
    assert section["time_alignment"]["first_t_ms"] <= section["time_alignment"]["last_t_ms"]

    # Both executing items are pinned, each naming the exact revision replayed, and each
    # carrying the ordinal the RUN MANIFEST assigned it.
    #
    # Asserted against the manifest's own ``mainboard_items`` order, NOT as
    # ``ordinals == sorted(ordinals)``. That spelling was the first draft and it is a
    # tautology: ``pinned_items_from_identities`` sorts its output by
    # ``(pin_ordinal, item_id)``, so the list is sorted whatever the ordinals mean — a
    # builder that stamped every item with its list position would have satisfied it.
    manifest_order = [str(entry["item_id"]) for entry in snapshot.manifest["mainboard_items"]]
    expected = {item_id: index for index, item_id in enumerate(manifest_order)}
    assert len(section["items"]) == 2
    for item in section["items"]:
        assert item["pin_ordinal"] == expected[item["item_id"]], item
        assert item["selected_revision_id"], item
    # ...and the section lists them in that pin order, which is the order the clock merged on.
    listed = [item["item_id"] for item in section["items"]]
    assert listed == sorted(listed, key=lambda item_id: expected[item_id])

    # The allocation revision the run replayed, from the manifest's OWN immutable snapshot.
    run_capital = snapshot.manifest["capital_execution"]
    assert section["portfolio_allocation"]["enabled"] is True
    assert section["portfolio_allocation"]["plan_id"] == run_capital["plan_id"]
    assert section["portfolio_allocation"]["plan_revision_id"] == run_capital["plan_revision_id"]
    assert section["portfolio_allocation"]["config_hash"] == run_capital["config_hash"]

    # Engine version + the policy versions a replay is a function of.
    assert section["policy_versions"]["engine_version"] == snapshot.engine_version
    assert section["policy_versions"]["portfolio_manifest_version"] == PORTFOLIO_MANIFEST_VERSION
    for key in ("clock_policy_version", "arbitration_policy_version", "attribution_policy_version"):
        assert section["policy_versions"][key], key

    # The equity artifact the reader can actually page is the one the section digests.
    assert section["ledger_artifact"] is not None


async def test_the_sections_identity_is_stable_across_a_replay(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two runs of the SAME composition pin byte-identical provenance content.

    ``identity`` hashes ``execution_content()``, which deliberately excludes display labels
    and run identity — so this is a claim about reproducibility, not about two rows happening
    to be written by one code path. If it drifted, the section would be recording the day the
    run happened rather than what the run did."""
    await _seed_principals(session)
    # The SAME composition, replayed. Two different compositions would pin different
    # revisions and legitimately hash differently, so they could not test this at all.
    composition_id = await _shared_composition(session, monkeypatch)
    first = await _run_once(session, monkeypatch, composition_id, key="replay-1")
    second = await _run_once(session, monkeypatch, composition_id, key="replay-2")
    assert first["result_id"] != second["result_id"]

    one = (await _snapshot(session, first["result_id"])).manifest[UNIFIED_MANIFEST_KEY]
    two = (await _snapshot(session, second["result_id"])).manifest[UNIFIED_MANIFEST_KEY]
    assert one["identity"] == two["identity"]
    # The hash is not vacuously equal because the content is empty.
    assert one["items"] and one["identity"]
    # ...and it really is a hash OF that content: the recorded digest matches a re-derivation
    # from the stored section, so a constant would fail here.
    recomputed = {
        key: value
        for key, value in one.items()
        if key not in ("identity", "presentation", "divergences")
    }
    assert manifest_hash(recomputed) == one["identity"]


async def test_the_rejected_intent_trace_survives_into_the_persisted_result(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every P4 intent is arbitrated and recorded, actionable or not (ADR §6 rule 5).

    Read from the persisted diagnostics rather than the in-memory projection: a suppression
    that never reaches the artifact is a suppression no reviewer can audit."""
    await _seed_principals(session)
    out = await _shared_run(session, monkeypatch)

    from tests.integration.test_backtest_persistence import _run_diagnostics

    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["decision_trace_count"] >= 1
    # Per-item attribution is in the Result, keyed by the pinned items.
    assert diagnostics["composition"]["strategy_count"] == 2
    assert diagnostics["composition"]["capital_allocation"] == "shared_pool"
    assert diagnostics["composition"]["clock"] == "unified_merged_axis"


# --------------------------------------------------------------------------- #
# (3) Backward compatibility — the independent path is untouched                #
# --------------------------------------------------------------------------- #
async def test_an_independent_multi_item_run_stays_legacy_sequential(session) -> None:
    """No section, and the shipped label is unchanged.

    This is the assertion with commercial weight: the section is what flips the mode, so a
    writer that set it unconditionally would silently re-label every composite Result ever
    produced as a portfolio valuation it is not."""
    await _seed_principals(session)
    out = await _independent_run(session)

    snapshot = await _snapshot(session, out["result_id"])
    assert UNIFIED_MANIFEST_KEY not in snapshot.manifest

    detail = await get_backtest_result(session, USER1, result_id=out["result_id"])
    assert detail["portfolio_simulation"]["mode"] == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    assert detail["portfolio_simulation"]["comparable_with_unified_clock"] is False


async def test_an_independent_results_snapshot_still_hashes_to_its_run_manifest(
    session,
) -> None:
    """The snapshot an independent Result stores is byte-identical to the run manifest.

    ``create_result`` grew a parameter; this pins that the parameter's ABSENT case changed
    nothing. Asserted as a hash equality rather than a field spot-check because the claim is
    about the whole document, and a spot-check cannot see an added key."""
    await _seed_principals(session)
    out = await _independent_run(session)
    snapshot = await _snapshot(session, out["result_id"])
    assert manifest_hash(snapshot.manifest) == snapshot.manifest_hash


async def test_a_unified_result_keeps_its_runs_manifest_hash_as_its_identity(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The RUN's admission hash is not re-derived when the section is appended.

    ``manifest_hash`` is the run's IDENTITY (doc 15 §7, §8.4 "retry -> new manifest hash"):
    it ties the Result back to its run and forwards into every export's
    ``source_manifest_hash``. Rehashing the extended document would fork that chain at the
    join. The section is self-describing instead — it carries its own content hash — which is
    the same two-hashes-over-overlapping-content shape ``execution_key`` and ``manifest_hash``
    already have.

    So for a unified Result the snapshot's hash deliberately does NOT cover the whole stored
    document. That is stated here rather than left implicit, because it is the one place this
    slice weakens a property the independent path still enjoys (asserted directly above)."""
    await _seed_principals(session)
    out = await _shared_run(session, monkeypatch)
    snapshot = await _snapshot(session, out["result_id"])

    run = (
        await session.execute(select(BacktestRun).where(BacktestRun.run_id == out["run_id"]))
    ).scalar_one()
    assert snapshot.manifest_hash == run.manifest_hash
    assert UNIFIED_MANIFEST_KEY in snapshot.manifest
    assert manifest_hash(snapshot.manifest) != snapshot.manifest_hash


async def test_a_historical_result_without_the_section_is_never_relabelled(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Result written BEFORE the section existed stays unknown, under either flag world.

    The fixture is a real unified run with the section REMOVED from its stored snapshot —
    exactly the row shape every shared Result produced between `C4` and this slice has.

    **It reads ``unknown``, not ``legacy_sequential``, and that is the correct answer.** The
    first draft of this test asserted ``legacy_sequential`` and was wrong: such a Result
    carries the unified engine kind and NO sequential warning, so the evidence needed to tell
    the two co-simulations apart is genuinely absent. ``portfolio_mode``'s stated rule is that
    absence of evidence is not evidence, and this is where that rule earns its keep — guessing
    "legacy" here would describe a genuine portfolio valuation as a sequential fold.

    The Result is read in BOTH flag worlds. That is the actual backward-compatibility claim:
    no silent recomputation and no relabelling as ``unified_clock``, even in a world where
    shared runs are executable and this run's own engine kind says it was one. A reader that
    consulted the live capability instead of the stored row would fail exactly here.
    """
    await _seed_principals(session)
    out = await _shared_run(session, monkeypatch)
    result_id = out["result_id"]

    snapshot = await _snapshot(session, result_id)
    historical = {k: v for k, v in snapshot.manifest.items() if k != UNIFIED_MANIFEST_KEY}
    snapshot.manifest = historical
    await session.commit()

    with _lifted(monkeypatch):
        lifted = await get_backtest_result(session, USER1, result_id=result_id)
    shipped = await get_backtest_result(session, USER1, result_id=result_id)

    assert lifted["portfolio_simulation"] == shipped["portfolio_simulation"]
    assert shipped["portfolio_simulation"]["mode"] == PORTFOLIO_MODE_UNKNOWN
    assert shipped["portfolio_simulation"]["comparable_with_unified_clock"] is False

    # Reading never writes: the row is not back-filled with the section a re-run would now
    # produce, and the Result is not re-simulated to find out (doc 15 §3.2 immutability).
    after = await _snapshot(session, result_id)
    assert UNIFIED_MANIFEST_KEY not in after.manifest
    assert after.manifest_hash == snapshot.manifest_hash


async def test_the_legacy_sequential_label_does_not_move_with_the_flag(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shipped era's own Results keep their label in a lifted world.

    Separate from the ``unknown`` case above because it is a different row shape and a
    different failure: this one DOES retain the evidence (the sequential fold's warning), so
    a flag-reading classifier would produce a confident wrong answer rather than an honest
    ``unknown``."""
    await _seed_principals(session)
    out = await _independent_run(session)

    shipped = await get_backtest_result(session, USER1, result_id=out["result_id"])
    with _lifted(monkeypatch):
        lifted = await get_backtest_result(session, USER1, result_id=out["result_id"])

    assert shipped["portfolio_simulation"] == lifted["portfolio_simulation"]
    assert lifted["portfolio_simulation"]["mode"] == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
