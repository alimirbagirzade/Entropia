"""A16 — the run manifest's policy provenance, and the parity that keeps it honest.

ADR 0002 §14 A16 requires the run manifest to carry the plan revision, the RESOLVED
sleeve amounts, the currency/FX refs, the compounding mode and four policy versions.
``C7`` ships that. This module pins the half a source-text tripwire cannot state.

**Why a parity test exists at all.** Each of the four policy versions is also defined by
the module that owns the policy, under ``execution/`` — the contained phase loop.
``domain/backtest/manifest.py`` sits outside that directory and MUST NOT import it: the
containment gate scans production source as text for the dotted ``execution.<module>
import`` spelling, and the per-module allowlists it holds are signed for exactly two
modules. So the manifest restates the values as literals, on the
``portfolio_mode.py::UNIFIED_MANIFEST_KEY`` precedent.

Restating a value is how a repo grows two answers to one question. A test file is not
scanned, so importing both sides here is free — which makes this the one place the drift
can be closed. ADIM 125 settled the general shape (one predicate, the expectation DERIVED
from it rather than restated); where a single shared symbol is structurally impossible,
this is that shape's remainder: the second spelling is not trusted, it is CHECKED against
the first.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.domain.backtest import manifest as manifest_mod
from entropia.domain.backtest.execution.arbitration import ARBITRATION_POLICY_VERSION
from entropia.domain.backtest.execution.clock import CLOCK_POLICY_VERSION
from entropia.domain.backtest.execution.provenance import (
    ENGINE_ALLOCATION_POLICY_VERSION,
    MARK_STALENESS_POLICY,
)
from entropia.domain.backtest.manifest import build_run_manifest


def _manifest(capital_mode: dict[str, Any] | None) -> dict[str, Any]:
    return build_run_manifest(
        run_id="btrun_1",
        composition_id="comp_1",
        composition_snapshot_id="snap_1",
        composition_fingerprint="fp_1",
        item_manifest={},
        capital_mode=capital_mode,
        requested_by_principal_id=None,
        preflight={},
        correlation_id=None,
        created_at_iso="2024-01-01T00:00:00Z",
    ).manifest


# --------------------------------------------------------------------------- #
# 1. The parity itself                                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("field", "owned_value"),
    [
        ("engine_allocation_policy_version", ENGINE_ALLOCATION_POLICY_VERSION),
        ("clock_policy_version", CLOCK_POLICY_VERSION),
        ("arbitration_policy_version", ARBITRATION_POLICY_VERSION),
        ("mark_staleness_policy", MARK_STALENESS_POLICY),
    ],
)
def test_each_manifest_policy_value_equals_the_owning_module(field: str, owned_value: str) -> None:
    """The restated literal must equal the value the contained layer owns.

    Parametrised per field on purpose: a single dict-equality assertion would report
    "the block differs" and leave the reader to find which of four strings drifted.
    """
    assert _manifest({"enabled": False})["portfolio_policy"][field] == owned_value


def test_the_block_names_exactly_the_four_fields_a16_lists() -> None:
    """Neither a missing field nor an extra one.

    The parametrised test above would stay green if a fifth key appeared, or if the
    block were built from a superset and A16's four happened to be right. A16 names a
    closed set; this asserts the set, not its members.
    """
    assert set(_manifest({"enabled": False})["portfolio_policy"]) == {
        "engine_allocation_policy_version",
        "clock_policy_version",
        "arbitration_policy_version",
        "mark_staleness_policy",
    }


def test_the_two_placements_of_the_block_cannot_disagree() -> None:
    """The block appears in the manifest body AND inside ``execution_content``.

    The second is not readable from the returned manifest (it is hashed away into
    ``execution_key``), so this proves the coupling the only way a caller can: changing
    the block must change the key. If the two placements were built from separate
    literals, one could move without the other and a Result would advertise a policy
    provenance its reproducibility identity did not carry.
    """
    baseline = build_run_manifest(
        run_id="btrun_1",
        composition_id="comp_1",
        composition_snapshot_id="snap_1",
        composition_fingerprint="fp_1",
        item_manifest={},
        capital_mode={"enabled": False},
        requested_by_principal_id=None,
        preflight={},
        correlation_id=None,
        created_at_iso="2024-01-01T00:00:00Z",
    )
    assert baseline.manifest["portfolio_policy"]["clock_policy_version"] == CLOCK_POLICY_VERSION
    # Same run identity, different engine version => different namespace. This is the
    # A15 mechanism the manifest's own comment relies on, asserted here against the
    # block rather than restated.
    shifted = build_run_manifest(
        run_id="btrun_1",
        composition_id="comp_1",
        composition_snapshot_id="snap_1",
        composition_fingerprint="fp_1",
        item_manifest={},
        capital_mode={"enabled": False},
        requested_by_principal_id=None,
        preflight={},
        correlation_id=None,
        created_at_iso="2024-01-01T00:00:00Z",
        engine_version="some-other-engine",
    )
    assert shifted.execution_key != baseline.execution_key


def test_the_policy_block_is_part_of_the_reproducibility_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing a policy version must move the ``execution_key``.

    ADDED BECAUSE A NEGATIVE CONTROL FOUND IT MISSING. Deleting
    ``"portfolio_policy": _portfolio_policy()`` from ``execution_content`` — while leaving
    it in the manifest body — left every other test in this file, the containment gate, the
    provenance tripwire and the integration proof GREEN. The only thing that noticed was the
    golden baseline, and its failure message says *"engine output changed ... fix the code,
    or bump ENGINE_VERSION and regenerate"*, which points a reader at the engine rather than
    at the manifest field that actually moved.

    ``execution_content`` is hashed away and never returned, so no caller can read it
    directly. This asserts the only observable consequence of membership: perturb a value
    the block is built from, and the reproducibility identity must move with it. Without
    that, two runs replayed under DIFFERENT policies would share an ``execution_key`` and
    the older Result would be idempotently returned for the newer question (INF-04/INF-05)
    — which is the entire reason A16 puts these four in the manifest.
    """
    baseline = build_run_manifest(
        run_id="btrun_1",
        composition_id="comp_1",
        composition_snapshot_id="snap_1",
        composition_fingerprint="fp_1",
        item_manifest={},
        capital_mode={"enabled": False},
        requested_by_principal_id=None,
        preflight={},
        correlation_id=None,
        created_at_iso="2024-01-01T00:00:00Z",
    )
    # Patch the module global the block is built from, NOT the emitted dict: that is what
    # a real policy change looks like, and it also proves the block is rebuilt per call
    # rather than frozen at import.
    monkeypatch.setattr(manifest_mod, "CLOCK_POLICY_VERSION", "clock-policy-v2")
    shifted = build_run_manifest(
        run_id="btrun_1",
        composition_id="comp_1",
        composition_snapshot_id="snap_1",
        composition_fingerprint="fp_1",
        item_manifest={},
        capital_mode={"enabled": False},
        requested_by_principal_id=None,
        preflight={},
        correlation_id=None,
        created_at_iso="2024-01-01T00:00:00Z",
    )
    assert shifted.manifest["portfolio_policy"]["clock_policy_version"] == "clock-policy-v2"
    assert shifted.execution_key != baseline.execution_key, (
        "the policy block is not part of execution_content: two runs under different "
        "clock policies would share a reproducibility namespace"
    )


# --------------------------------------------------------------------------- #
# 2. The allocation half of A16                                                #
# --------------------------------------------------------------------------- #
def test_the_manifest_carries_the_resolved_sleeve_amounts_and_fx_refs() -> None:
    """§10.1's two genuinely-missing groups, as the admission snapshot now supplies them.

    ``capital_execution`` is passed through verbatim, so this pins the CONTRACT the
    manifest offers a reader. That the admission path actually fills these in is a
    different claim, proved end-to-end in
    ``tests/integration/test_allocation_manifest_provenance.py``.
    """
    capital_mode = {
        "enabled": True,
        "plan_id": "plan_1",
        "plan_revision_id": "planrev_1",
        "config_hash": "0" * 64,
        "config": {"compounding_mode": "COMPOUND", "initial_capital": "10000.00"},
        "derived_amounts": {
            "currency": "USD",
            "portfolio_initial_capital": "10000.00",
            "reserved_cash": "1000.00",
            "capital_available": "9000.00",
            "total_allocated": "9000.00",
            "unallocated": "0.00",
            "active_share_total": "100.00",
            "sleeves": [
                {
                    "composition_item_id": "item_1",
                    "equity_share_percent": "40.00",
                    "initial_sleeve_capital": "3600.00",
                }
            ],
        },
        "settlement_currencies": {"item_1": "USD"},
    }
    pinned = _manifest(capital_mode)["capital_execution"]
    assert pinned["plan_revision_id"] == "planrev_1"
    # The RESOLVED money, not the share percent. The percent was always pinned inside
    # ``config``; the resolved sleeve capital is what §10.1 says was missing.
    assert pinned["derived_amounts"]["sleeves"][0]["initial_sleeve_capital"] == "3600.00"
    assert pinned["settlement_currencies"] == {"item_1": "USD"}


def test_the_compounding_mode_is_pinned_through_the_config_and_is_not_duplicated() -> None:
    """A16 lists the compounding mode; it was ALREADY pinned, and that was measured.

    ADR §10.1 says the shipped snapshot carries "only ``{enabled, plan_id,
    plan_revision_id, config_hash, config}``" — true at the TOP level, and easy to read as
    "the compounding mode is missing". It is not: ``canonical_config`` is
    ``config.model_dump(mode="json")`` and ``compounding_mode`` is a field of
    ``PortfolioAllocationConfigV1``, so it ships inside ``config`` and is hashed into
    ``config_hash``.

    So ``C7`` does NOT add a second spelling of it. Echoing it beside ``config`` would
    create exactly the drift the parity test above exists to prevent, in a place no test
    could later distinguish from the real one. This asserts the reachable path instead,
    so that a future refactor which drops it from the config is still a red build.
    """
    pinned = _manifest(
        {
            "enabled": True,
            "config": {"compounding_mode": "COMPOUND"},
            "derived_amounts": None,
            "settlement_currencies": None,
        }
    )["capital_execution"]
    assert pinned["config"]["compounding_mode"] == "COMPOUND"
    assert "compounding_mode" not in pinned, (
        "the compounding mode gained a second spelling beside the config it already "
        "ships in; two spellings drift, and config_hash only covers one of them"
    )


def test_an_independent_run_still_carries_the_policy_block() -> None:
    """The four versions are engine-wide, not allocation-scoped.

    An independent composition has no plan, so ``capital_execution`` is ``{"enabled":
    False}`` and carries no allocation provenance — but the run was still produced under
    a particular clock/arbitration/mark policy, and a Result that cannot say which is
    exactly the gap A16 names.
    """
    manifest = _manifest({"enabled": False})
    assert manifest["capital_execution"] == {"enabled": False}
    assert manifest["portfolio_policy"]["clock_policy_version"] == CLOCK_POLICY_VERSION
