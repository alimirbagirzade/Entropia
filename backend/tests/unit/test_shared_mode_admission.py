"""ADR 0002 §13.1 OD-1(a) / OD-6(a) — the shared-mode admission predicates.

These are the plan-level refusals `C6` owes: a composition the unified loop cannot
model, refused before a run exists. The wiring proof (a real admission actually
refusing and leaving nothing behind) is
``tests/integration/test_shared_mode_admission.py``; this file pins the DECISIONS.

Every refusal case below is paired with a negative control in the same block — a
config that differs only in the offending fact and must come back clean. Without
that pairing a predicate that simply returned everything would pass the refusal
half of this file.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.domain.allocation import capability
from entropia.domain.allocation.rules import ALLOCATABLE_ITEM_KINDS
from entropia.domain.allocation.shared_mode_admission import (
    EXECUTING_ITEM_KINDS,
    declared_record_time_bases,
    mixed_record_time_bases,
    non_executing_sleeve_holders,
)
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import ReadinessIssueCode as Code
from entropia.domain.readiness.enums import ReadinessScope as Scope
from entropia.domain.readiness.enums import ReadinessSeverity as Sev
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.domain.readiness.validators import (
    evaluate_readiness,
    shared_mode_execution_issues,
)
from entropia.domain.strategy.config import StrategyConfig

from .oracles.harness import oracle_config


def _snapshot(*entries: dict[str, Any]) -> dict[str, Any]:
    """An immutable capital snapshot in the shape ``_resolve_allocation`` writes."""
    return {
        "enabled": True,
        "plan_id": "allocplan_1",
        "plan_revision_id": "allocrev_1",
        "config_hash": "deadbeef",
        "config": {"enabled": True, "entries": list(entries)},
    }


def _entry(
    item_id: str,
    item_type: str | None,
    *,
    active: bool = True,
    share: str | None = "50",
) -> dict[str, Any]:
    return {
        "composition_item_id": item_id,
        "item_type": item_type,
        "active": active,
        "equity_share_percent": share,
    }


def _data_time(*bases: str | None) -> list[dict[str, Any]]:
    """One ``data_time`` row per basis; ``None`` means the revision declares none."""
    return [
        {
            "item_id": f"mbitem_{index}",
            "market_dataset": None if basis is None else {"record_time_basis": basis},
        }
        for index, basis in enumerate(bases)
    ]


# --------------------------------------------------------------------------- #
# The executing set — stated positively so a widened enum fails CLOSED         #
# --------------------------------------------------------------------------- #


def test_only_strategy_executes_and_the_complement_is_the_allocatable_rest() -> None:
    """Strategy is the only kind the worker simulates (``output=None`` for the rest)."""
    assert frozenset({MainboardItemKind.STRATEGY}) == EXECUTING_ITEM_KINDS
    assert {
        MainboardItemKind.TRADING_SIGNAL,
        MainboardItemKind.TRADE_LOG,
    } == ALLOCATABLE_ITEM_KINDS - EXECUTING_ITEM_KINDS


def test_an_unknown_future_kind_is_treated_as_non_executing() -> None:
    """The fail-closed direction, and the reason the set is written positively.

    A kind this build has never heard of cannot be known to execute, so it must be
    refused a sleeve rather than silently earning one. Had the module listed the
    NON-executing kinds instead, this row would sail through.
    """
    holders = non_executing_sleeve_holders(_snapshot(_entry("mbitem_x", "quantum_oracle")))
    assert holders == ("mbitem_x",)


# --------------------------------------------------------------------------- #
# OD-6(a) — a non-executing kind holding a sleeve                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("kind", ["trading_signal", "trade_log"])
def test_a_non_executing_kind_holding_a_positive_share_is_an_offender(kind: str) -> None:
    snapshot = _snapshot(
        _entry("mbitem_strategy", "strategy", share="60"),
        _entry("mbitem_external", kind, share="40"),
    )
    assert non_executing_sleeve_holders(snapshot) == ("mbitem_external",)


def test_a_strategy_only_plan_is_clean() -> None:
    """NEGATIVE CONTROL: the legal shape must produce no finding."""
    snapshot = _snapshot(
        _entry("mbitem_a", "strategy", share="60"),
        _entry("mbitem_b", "strategy", share="40"),
    )
    assert non_executing_sleeve_holders(snapshot) == ()


def test_an_inactive_external_entry_is_not_an_offender() -> None:
    """ADR names ACTIVE entries; a deactivated row claims nothing from the pool."""
    snapshot = _snapshot(
        _entry("mbitem_strategy", "strategy", share="100"),
        _entry("mbitem_external", "trade_log", active=False, share="40"),
    )
    assert non_executing_sleeve_holders(snapshot) == ()


@pytest.mark.parametrize("share", [None, "0", "0.00"])
def test_an_external_entry_claiming_no_capital_is_not_an_offender(share: str | None) -> None:
    """OD-6's harm is a positive share that silently does nothing.

    A null or zero share withholds nothing from the items that can trade, and is
    already ``validate_allocation``'s finding rather than this one.
    """
    snapshot = _snapshot(_entry("mbitem_external", "trade_log", share=share))
    assert non_executing_sleeve_holders(snapshot) == ()


def test_an_unparseable_share_fails_closed() -> None:
    """A malformed row is refused, not waved through on a parse error."""
    snapshot = _snapshot(_entry("mbitem_external", "trade_log", share="not-a-number"))
    assert non_executing_sleeve_holders(snapshot) == ("mbitem_external",)


def test_an_entry_with_no_recorded_kind_yields_nothing() -> None:
    """An unrecorded kind is not evidence of a non-executing one (already UNAVAILABLE)."""
    assert non_executing_sleeve_holders(_snapshot(_entry("mbitem_x", None))) == ()


def test_every_offender_is_reported_in_snapshot_order() -> None:
    """The envelope promotes ONE leader, so ``details`` must carry the rest (O-02)."""
    snapshot = _snapshot(
        _entry("mbitem_signal", "trading_signal", share="30"),
        _entry("mbitem_strategy", "strategy", share="40"),
        _entry("mbitem_log", "trade_log", share="30"),
    )
    assert non_executing_sleeve_holders(snapshot) == ("mbitem_signal", "mbitem_log")


@pytest.mark.parametrize(
    "capital",
    [None, {}, {"enabled": True}, {"config": None}, {"config": {"entries": "nope"}}, "string"],
)
def test_an_unreadable_capital_snapshot_yields_no_offenders(capital: Any) -> None:
    """A snapshot that cannot be read is not evidence of a violation.

    The caller has already established that shared capital was REQUESTED; inventing
    an offender out of a shape mismatch would refuse runs for the wrong reason.
    """
    assert non_executing_sleeve_holders(capital) == ()


# --------------------------------------------------------------------------- #
# OD-1(a) — pinned revisions declaring different record time bases             #
# --------------------------------------------------------------------------- #


def test_two_different_bases_are_reported_sorted() -> None:
    assert mixed_record_time_bases(_data_time("bar_open", "bar_close")) == (
        "bar_close",
        "bar_open",
    )


def test_three_different_bases_are_all_reported() -> None:
    bases = mixed_record_time_bases(_data_time("event_time", "bar_open", "bar_close"))
    assert bases == ("bar_close", "bar_open", "event_time")


def test_one_basis_pinned_twice_is_clean() -> None:
    """NEGATIVE CONTROL: agreeing revisions are the legal shape."""
    assert mixed_record_time_bases(_data_time("bar_close", "bar_close")) == ()


def test_a_single_item_is_clean() -> None:
    assert mixed_record_time_bases(_data_time("bar_close")) == ()


def test_no_strategy_items_is_clean() -> None:
    assert mixed_record_time_bases([]) == ()


def test_an_absent_declaration_is_not_a_second_convention() -> None:
    """A revision that declares nothing must not COUNT as a rival basis.

    Bucketing ``None`` would block a composition for a provenance GAP instead of for
    a conflict — a different defect, with a different remedy.
    """
    assert declared_record_time_bases(_data_time("bar_close", None)) == ("bar_close",)
    assert mixed_record_time_bases(_data_time("bar_close", None)) == ()
    assert mixed_record_time_bases(_data_time(None, None)) == ()


def test_a_malformed_data_time_row_is_ignored() -> None:
    rows: list[Any] = ["not-a-dict", {"market_dataset": "not-a-dict"}, {}]
    assert declared_record_time_bases(rows) == ()


# --------------------------------------------------------------------------- #
# G11 (P2) / G12 (P8) — the issue SHAPE the two signed gates speak with        #
# --------------------------------------------------------------------------- #

_DEFERRED = Code.ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED
_SCALING = Code.ALLOCATION_SHARED_MODE_SCALING_UNSUPPORTED
_TOGGLE = "enabled"

_SCALING_ON: dict[str, Any] = {
    "enabled": True,
    "method": "price_distance_scaling",
    "price_scaling": {"retracement_distance": "1", "layers": 2},
    "add_size": "percent_of_initial",
    "add_size_value": "50",
}


def _config(**kwargs: Any) -> StrategyConfig:
    return oracle_config(direction="long", conflict={"same_direction_stacking": "ignore"}, **kwargs)


def _strategy_item(item_id: str, config: StrategyConfig, **overrides: Any) -> ReadinessItemInput:
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.STRATEGY,
        root_id=f"root_{item_id}",
        revision_id=f"rev_{item_id}",
        available=overrides.pop("available", True),
        payload=overrides.pop("payload", config.model_dump(mode="json")),
    )


def test_a_clean_shared_composition_produces_no_shape_issues() -> None:
    """The negative control the whole block is measured against."""
    assert shared_mode_execution_issues([("mbitem_1", _config())]) == []


def test_a_deferring_timing_names_the_setting_the_item_and_the_gate() -> None:
    issues = shared_mode_execution_issues([("mbitem_1", _config(entry_timing="next_candle_open"))])
    lead = issues[0]
    assert lead.code == _DEFERRED
    assert lead.severity == Sev.BLOCKER
    # The POOL is what makes this configuration a finding — the same Strategy is legal
    # and fully modelled in independent mode — so the pool is the layer that reports it.
    assert lead.scope == Scope.PORTFOLIO_ALLOCATION
    assert lead.field_path == "data.execution.entry_timing"
    assert lead.scope_id == "mbitem_1"
    assert lead.remediation


def test_scaling_speaks_with_its_own_code_not_the_fill_one() -> None:
    """Two signatures, two codes. Collapsing them would make the Ready Check page unable
    to say WHICH gate refused, and either could be revisited without the other."""
    issues = shared_mode_execution_issues([("mbitem_1", _config(scaling=_SCALING_ON))])
    assert [i.code for i in issues] == [_SCALING, _SCALING]
    assert issues[0].field_path == "scaling_logic.enabled"


def test_the_envelope_leader_is_a_setting_and_the_toggle_row_closes_the_list() -> None:
    """G11 §Karar's ``field_path`` sub-decision, "ikisi de", made concrete.

    O-02 promotes the FIRST blocker onto the 422 envelope, so the first row has to be the
    setting the user must change; the toggle — the other half of the fix, and the only
    field that resolves every item at once — closes the list. Both field paths therefore
    appear in ``details``, which is exactly what "ikisi de" asks for.
    """
    issues = shared_mode_execution_issues(
        [("mbitem_1", _config(entry_timing="next_candle_open", exit_timing="next_candle_close"))]
    )
    assert [i.field_path for i in issues] == [
        "data.execution.entry_timing",
        "data.execution.exit_timing",
        _TOGGLE,
    ]
    # The toggle row is a COMPOSITION-level statement: no single item is the fault the
    # reader would act on, so it claims no scope_id and would not blame one item.
    assert issues[-1].scope_id is None
    assert issues[-1].code == _DEFERRED


def test_the_toggle_row_appears_once_per_violated_gate_not_once_per_violation() -> None:
    """Three offending settings across two items still summarise to two toggle rows —
    one per gate. One per violation would repeat the same sentence five times."""
    issues = shared_mode_execution_issues(
        [
            ("mbitem_1", _config(entry_timing="next_candle_open", scaling=_SCALING_ON)),
            ("mbitem_2", _config(exit_timing="intrabar_touch")),
        ]
    )
    toggle_rows = [i for i in issues if i.field_path == _TOGGLE]
    assert [i.code for i in toggle_rows] == [_DEFERRED, _SCALING]


def test_every_offending_item_is_named_so_a_user_can_find_them_all() -> None:
    """Reporting only the first offender would send a user round the loop once per item."""
    issues = shared_mode_execution_issues(
        [
            ("mbitem_1", _config(entry_timing="next_candle_open")),
            ("mbitem_2", _config()),
            ("mbitem_3", _config(entry_timing="intrabar_touch")),
        ]
    )
    assert [i.scope_id for i in issues if i.scope_id] == ["mbitem_1", "mbitem_3"]


# --------------------------------------------------------------------------- #
# ... and when Ready Check is allowed to say it at all                         #
# --------------------------------------------------------------------------- #


def _codes(items: list[ReadinessItemInput], *, allocation_enabled: bool) -> set[str]:
    evaluation = evaluate_readiness(
        items, allocation_enabled=allocation_enabled, allocation_issues=[]
    )
    return {str(issue.code) for issue in evaluation.issues}


def test_ready_check_is_silent_while_containment_is_on() -> None:
    """SHIPPED WORLD. The one true finding for an enabled plan today is the containment
    blocker: shared mode is not unavailable *for this Strategy*, it is unavailable at
    all. Stacking three more blockers behind it would bury the actionable one and tell
    the user to edit a Strategy that is not the reason the run is refused."""
    assert not capability.shared_allocation_is_executable()
    item = _strategy_item("mbitem_1", _config(entry_timing="next_candle_open"))
    assert _DEFERRED.value not in _codes([item], allocation_enabled=True)


def test_ready_check_reports_the_blockers_once_the_flag_lifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIFTED WORLD — the one `C9` will ship. Without this the guard above would be
    indistinguishable from one that never reports anything at all."""
    item = _strategy_item("mbitem_1", _config(entry_timing="next_candle_open"))
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        assert _DEFERRED.value in _codes([item], allocation_enabled=True)


def test_an_independent_composition_is_never_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """NEGATIVE CONTROL for the lift test: independent mode replays each item on its own
    ledger, where a deferred fill is fully modelled. Doc 13 §1.1 — a complete mode."""
    item = _strategy_item("mbitem_1", _config(entry_timing="next_candle_open"))
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        assert _DEFERRED.value not in _codes([item], allocation_enabled=False)


def test_an_unavailable_or_unparseable_item_yields_no_derived_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A soft-deleted pin is already ``ITEM_UNAVAILABLE`` and an unparseable config is
    already ``STRATEGY_CONFIG_INVALID``. Guessing at either would report a second,
    derived finding for one defect — and would have to guess at fields that are absent."""
    config = _config(entry_timing="next_candle_open")
    unavailable = _strategy_item("mbitem_1", config, available=False)
    unparseable = _strategy_item("mbitem_2", config, payload={"strategy_root_id": "only"})
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        codes = _codes([unavailable, unparseable], allocation_enabled=True)
    assert _DEFERRED.value not in codes
