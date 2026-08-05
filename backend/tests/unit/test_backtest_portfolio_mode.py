"""ADIM 19 — which co-simulation produced a persisted Result.

The property under test is HISTORICAL INTEGRITY (ADR 0002 §10.4, doc 13 §14 test 19): the
label must come from the Result's own pinned manifest and its own pinned diagnostics, so
nothing that can change later — the live composition, the live capability flag — can
re-interpret a Result that already exists.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.domain.allocation import capability
from entropia.domain.allocation.capability import LEGACY_SEQUENTIAL_RESULT_NOTE
from entropia.domain.backtest.execution.portfolio import COMPOSITION_CURVE_WARNING
from entropia.domain.backtest.portfolio_mode import (
    COMPOSITION_ENGINE_KIND,
    PORTFOLIO_MODE_LEGACY_SEQUENTIAL,
    PORTFOLIO_MODE_SINGLE_ITEM,
    PORTFOLIO_MODE_UNIFIED_CLOCK,
    PORTFOLIO_MODE_UNKNOWN,
    PORTFOLIO_MODES,
    SINGLE_ITEM_ENGINE_KIND,
    UNIFIED_CLOCK_NOTE,
    UNIFIED_MANIFEST_KEY,
    UNKNOWN_MODE_NOTE,
    portfolio_simulation_context,
    portfolio_simulation_note,
    resolve_portfolio_simulation_mode,
)


def _legacy_diagnostics(strategy_count: int = 3) -> dict[str, Any]:
    return {
        "warnings": [COMPOSITION_CURVE_WARNING],
        "composition": {"strategy_count": strategy_count},
    }


def _unified_manifest() -> dict[str, Any]:
    return {
        "identity": {"engine_version": "backtest-engine-vNEXT"},
        UNIFIED_MANIFEST_KEY: {
            "policy_versions": {"portfolio_manifest_version": "portfolio-manifest-v1"}
        },
    }


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def test_a_shipped_multi_item_result_is_labelled_legacy_sequential() -> None:
    assert (
        resolve_portfolio_simulation_mode({}, _legacy_diagnostics())
        == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    )


def test_a_single_item_result_needs_no_portfolio_characterisation() -> None:
    diagnostics = {"warnings": [], "composition": {"strategy_count": 1}}
    assert resolve_portfolio_simulation_mode({}, diagnostics) == PORTFOLIO_MODE_SINGLE_ITEM


def test_the_single_item_bypass_is_recognised_from_engine_kind_alone() -> None:
    """The single-item path emits NO ``composition`` block (``execution/output.py:369``
    vs ``execution/portfolio.py:570``), so without ``engine_kind`` a one-item Result would
    be indistinguishable from one whose diagnostics were never retained."""
    diagnostics = {"engine_kind": SINGLE_ITEM_ENGINE_KIND, "warnings": []}
    assert "composition" not in diagnostics
    assert resolve_portfolio_simulation_mode({}, diagnostics) == PORTFOLIO_MODE_SINGLE_ITEM


def test_the_composite_engine_kind_alone_does_not_claim_single_item() -> None:
    diagnostics = {"engine_kind": COMPOSITION_ENGINE_KIND, "warnings": []}
    assert resolve_portfolio_simulation_mode({}, diagnostics) == PORTFOLIO_MODE_UNKNOWN


def test_the_sequential_warning_outranks_engine_kind() -> None:
    """A composite fold that also carries the curve warning is legacy, not unknown."""
    diagnostics = {
        "engine_kind": COMPOSITION_ENGINE_KIND,
        "warnings": [COMPOSITION_CURVE_WARNING],
        "composition": {"strategy_count": 2},
    }
    assert resolve_portfolio_simulation_mode({}, diagnostics) == PORTFOLIO_MODE_LEGACY_SEQUENTIAL


def test_a_pinned_unified_manifest_section_wins() -> None:
    assert (
        resolve_portfolio_simulation_mode(_unified_manifest(), None) == PORTFOLIO_MODE_UNIFIED_CLOCK
    )


def test_the_pinned_manifest_outranks_a_contradictory_sequential_warning() -> None:
    """A unified run should never emit the sequential-curve warning (ADR 0002 §15 retires
    it), so the combination is contradictory. The PINNED manifest is the stronger evidence
    and must win — otherwise a stale warning could demote a genuine unified Result."""
    assert (
        resolve_portfolio_simulation_mode(_unified_manifest(), _legacy_diagnostics())
        == PORTFOLIO_MODE_UNIFIED_CLOCK
    )


def test_a_result_with_no_retained_diagnostics_is_unknown_not_legacy() -> None:
    """Absence of evidence is not evidence: an undiagnosed Result must not be asserted
    to be a sequential fold."""
    assert resolve_portfolio_simulation_mode({}, None) == PORTFOLIO_MODE_UNKNOWN
    assert resolve_portfolio_simulation_mode(None, None) == PORTFOLIO_MODE_UNKNOWN
    assert resolve_portfolio_simulation_mode({}, {}) == PORTFOLIO_MODE_UNKNOWN


@pytest.mark.parametrize(
    "diagnostics",
    [
        pytest.param({"warnings": "not-a-list"}, id="warnings-not-a-list"),
        pytest.param({"composition": "not-a-dict"}, id="composition-not-a-dict"),
        pytest.param({"composition": {"strategy_count": "3"}}, id="count-not-an-int"),
        pytest.param([], id="diagnostics-not-a-dict"),
    ],
)
def test_a_malformed_diagnostics_blob_degrades_to_unknown(diagnostics: Any) -> None:
    assert resolve_portfolio_simulation_mode({}, diagnostics) == PORTFOLIO_MODE_UNKNOWN


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param({UNIFIED_MANIFEST_KEY: {}}, id="section-without-versions"),
        pytest.param(
            {UNIFIED_MANIFEST_KEY: {"policy_versions": {}}}, id="versions-without-the-field"
        ),
        pytest.param(
            {UNIFIED_MANIFEST_KEY: {"policy_versions": {"portfolio_manifest_version": ""}}},
            id="blank-version",
        ),
        pytest.param({UNIFIED_MANIFEST_KEY: "not-a-dict"}, id="section-not-a-dict"),
    ],
)
def test_a_half_written_unified_section_does_not_claim_unified(manifest: dict[str, Any]) -> None:
    """Only a real pinned version counts. A truncated section must not upgrade the label."""
    assert resolve_portfolio_simulation_mode(manifest, None) == PORTFOLIO_MODE_UNKNOWN
    assert (
        resolve_portfolio_simulation_mode(manifest, _legacy_diagnostics())
        == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    )


# --------------------------------------------------------------------------- #
# historical integrity — the live flag must not re-label a stored Result
# --------------------------------------------------------------------------- #
def test_flipping_the_live_capability_flag_cannot_relabel_a_stored_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """doc 13 §14 test 19 / ADR 0002 §10.4. The resolver never reads the flag, and this
    proves it by flipping the flag to its opposite and re-classifying the SAME inputs."""
    diagnostics = _legacy_diagnostics()
    before = resolve_portfolio_simulation_mode({}, diagnostics)
    monkeypatch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
    assert capability.shared_allocation_is_executable() is True
    assert resolve_portfolio_simulation_mode({}, diagnostics) == before

    unified = _unified_manifest()
    monkeypatch.setattr(capability, "SHARED_ALLOCATION_STATUS", "future_dev")
    assert resolve_portfolio_simulation_mode(unified, None) == PORTFOLIO_MODE_UNIFIED_CLOCK


def test_the_resolver_reads_nothing_beyond_its_two_arguments() -> None:
    """A live composition join would need a session or a repository import. There is none."""
    from entropia.domain.backtest import portfolio_mode

    source = portfolio_mode.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in ("AsyncSession", "repositories", "shared_allocation_is_executable", "await "):
        assert forbidden not in text, f"{forbidden!r} would make the label re-interpretable"


# --------------------------------------------------------------------------- #
# reader-facing notes
# --------------------------------------------------------------------------- #
def test_the_legacy_note_is_the_shipped_constant_not_a_second_copy() -> None:
    """``LEGACY_SEQUENTIAL_RESULT_NOTE`` existed and was never consumed; ADR 0002 §10.4
    requires exactly this label at read time."""
    assert (
        portfolio_simulation_note(PORTFOLIO_MODE_LEGACY_SEQUENTIAL) == LEGACY_SEQUENTIAL_RESULT_NOTE
    )
    assert "sequential approximation" in LEGACY_SEQUENTIAL_RESULT_NOTE


def test_every_mode_has_a_note_and_an_unknown_token_has_none() -> None:
    for mode in PORTFOLIO_MODES:
        assert portfolio_simulation_note(mode)
    assert portfolio_simulation_note("not-a-mode") is None


def test_the_context_states_comparability_rather_than_leaving_it_to_be_inferred() -> None:
    legacy = portfolio_simulation_context({}, _legacy_diagnostics())
    assert legacy["mode"] == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    assert legacy["note"] == LEGACY_SEQUENTIAL_RESULT_NOTE
    assert legacy["comparable_with_unified_clock"] is False

    unified = portfolio_simulation_context(_unified_manifest(), None)
    assert unified["mode"] == PORTFOLIO_MODE_UNIFIED_CLOCK
    assert unified["note"] == UNIFIED_CLOCK_NOTE
    assert unified["comparable_with_unified_clock"] is True

    unknown = portfolio_simulation_context({}, None)
    assert unknown["note"] == UNKNOWN_MODE_NOTE
    assert unknown["comparable_with_unified_clock"] is False


def test_the_context_shape_is_stable() -> None:
    assert set(portfolio_simulation_context({}, None)) == {
        "mode",
        "note",
        "comparable_with_unified_clock",
    }
