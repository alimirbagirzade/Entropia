"""Strategy Details API + compiler contract tests (doc 02 §7, §8).

Two DB-free surfaces are asserted here (DB-touching flows live in
tests/integration/test_strategy_integration.py):

* The API contract — the page is authentication-gated (Guest create -> 401, no
  leak) and pure input validation rejects a blank display_name before any DB work
  (422). DI-override style mirrors test_mainboard_contract.py.
* The compiler contract — ``config_hash`` is deterministic, disabled sections are
  filtered out (scaling.enabled=false -> None), and the cross-field blockers
  (sizing exclusivity, trigger-source-conditional) surface their machine codes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.strategy.compiler import (
    CODE_SIZING_NOT_EXCLUSIVE,
    CODE_TRIGGER_CONDITION_REQUIRED,
    compute_config_hash,
    validate_semantics,
    validate_strategy_config,
)

_HASH = "a" * 64
_PKG_HASH = "f" * 64


class _DummySession:
    """Stand-in; guest + pure-validation paths never touch it."""


def _actor(role: Role | None, ptype: PrincipalType, pid: str | None) -> Actor:
    return Actor(principal_id=pid, principal_type=ptype, role=role)


def _override(app: Any, actor: Actor) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),  # type: ignore[arg-type]
        actor=actor,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _valid_payload() -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_x",
        "display_name": "Contract Strategy",
        "rationale_family_id": "ratfam_x",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "mkt",
            "market_dataset_revision_id": "mrev",
            "market_dataset_content_hash": _HASH,
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
            "initial_capital": "10000.00",
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_close"},
            "order_config": {"type": "market_order", "limit": None},
            "costs": {
                "commission": "0.001",
                "spread": "0.0002",
                "slippage_mode": "percentage_slippage",
                "slippage_value": "0.01",
            },
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "direction_mode": "long_and_short",
            "signal_block": {
                "rule": "required_indicator_blocks_only",
                "min_supporting_count": None,
            },
            "indicator_blocks": [
                {
                    "block_id": "ind",
                    "display_order": 0,
                    "enabled": True,
                    "package_ref": {
                        "package_root_id": "pkg",
                        "package_revision_id": "pkgrev",
                        "package_content_hash": _PKG_HASH,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "direction": "long",
                    "timeframe": "same_as_base_tf",
                    "validity": "3_candles",
                    "requirement": "required",
                    "condition_block_rule": None,
                    "min_supporting_condition_count": None,
                    "condition_blocks": None,
                    "parameter_overrides": None,
                }
            ],
        },
        "position_exit_logic": {
            "applies_to_direction": "long_and_short",
            "close_percentage": "100",
            "partial_aftermath": "move_stop_to_entry",
            "signal_block": None,
            "indicator_blocks": None,
        },
        "protection_stop_logic": {
            "percentage_stop": {"enabled": True, "loss_percentage": "1.0"},
            "trailing_stop": None,
            "absolute_stop": None,
        },
        "position_sizing": {
            "method": "base_position_size",
            "base_position_size": "100.0",
            "risk_based": None,
            "formula_based": None,
            "signal_strength_adjustment": "no_adjustment",
            "leverage_mode": "isolated",
            "position_size_limits": None,
        },
        "scaling_logic": {
            "enabled": False,
            "timeframe": "same_as_base_tf",
            "method": None,
            "price_scaling": None,
            "logic_scaling": None,
            "add_size": "percent_of_initial",
            "add_size_value": None,
            "scaling_limits": None,
        },
        "restrictions_filters": {"rule": "any", "filters": []},
        "conflict_position_handling": {
            "overlapping_signal_policy": "queue_sequential",
            "same_direction_stacking": "allow_stacking",
            "opposite_direction_hedge": "allow_hedge",
            "exit_on_opposite_signal": True,
        },
    }


# --------------------------------------------------------------------------- #
# API contract (DB-free)                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.contract
async def test_guest_cannot_create_strategy_draft(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/strategy-drafts", json={"display_name": "X"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_create_strategy_draft_requires_display_name(app) -> None:
    # Pure input validation rejects a blank name BEFORE any DB work (422).
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/strategy-drafts", json={"display_name": "   "})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        next(gen, None)


# --------------------------------------------------------------------------- #
# Compiler contract (pure)                                                     #
# --------------------------------------------------------------------------- #


def test_config_hash_is_deterministic_and_content_sensitive() -> None:
    config_a, issues_a = validate_strategy_config(_valid_payload())
    config_b, _ = validate_strategy_config(_valid_payload())
    assert config_a is not None and not issues_a
    assert config_b is not None
    h1 = compute_config_hash(config_a)
    h2 = compute_config_hash(config_b)
    assert h1 == h2 and len(h1) == 64

    changed = _valid_payload()
    changed["display_name"] = "A Different Name"
    config_c, _ = validate_strategy_config(changed)
    assert config_c is not None
    assert compute_config_hash(config_c) != h1


def test_disabled_scaling_is_filtered_to_none() -> None:
    config, issues = validate_strategy_config(_valid_payload())
    assert config is not None and not issues
    # scaling.enabled=false -> the whole subtree is dropped (Binding Decision #2).
    assert config.scaling_logic is None


def test_compiler_flags_sizing_not_exclusive() -> None:
    payload = _valid_payload()
    payload["position_sizing"]["risk_based"] = {
        "risk_percentage_per_trade": "1.0",
        "stop_loss_point": "50.0",
    }
    config, issues = validate_strategy_config(payload)
    assert config is not None  # structurally valid; blocked semantically
    assert CODE_SIZING_NOT_EXCLUSIVE in {i["code"] for i in issues}


def test_compiler_flags_trigger_source_condition_required() -> None:
    payload = _valid_payload()
    payload["position_entry_logic"]["indicator_blocks"][0]["trigger_source"] = (
        "indicator_native_trigger_plus_condition"
    )
    config, issues = validate_strategy_config(payload)
    assert config is not None
    assert CODE_TRIGGER_CONDITION_REQUIRED in {i["code"] for i in issues}


def test_native_trigger_needs_no_condition() -> None:
    # A Native-only trigger with zero conditions is valid (AT-05 positive case).
    config, _issues = validate_strategy_config(_valid_payload())
    assert config is not None
    assert not validate_semantics(config)
