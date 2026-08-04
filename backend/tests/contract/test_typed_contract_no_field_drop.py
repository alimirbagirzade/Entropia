"""No-field-drop guard for the ESP / Library / Agent-Tool-Gateway response models.

``response_model`` FILTERS the body to the declared fields: a key the serializer emits but
the model omits disappears from the wire silently, with no error anywhere. Adding a key to
a serializer is a one-line change that nobody would think to mirror into a Pydantic model —
so this module pins every typed model against the REAL serializer that feeds it.

The serializers exercised here are pure functions over ORM attributes, so they run with
lightweight stubs and no database. Command envelopes (which need a transaction) are locked
by ``tests/integration/test_typed_contract_replay_parity.py`` instead.

The frozen key sets are deliberately spelled out rather than derived: a test that computed
the expectation from the model under test would pass no matter what either side did.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from entropia.application.queries import agent_tool_gateway as tg_query
from entropia.application.queries import esp as esp_query
from entropia.application.queries import library as library_query
from entropia.apps.api.schemas import agent_tool_gateway as tg_schema
from entropia.apps.api.schemas import esp as esp_schema
from entropia.apps.api.schemas import library as library_schema
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.esp.validation import ResolverCheck
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.export_contract import build_registry_observation
from entropia.domain.package.permissions import PackagePermissions

pytestmark = pytest.mark.contract


def _fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


# ---------------------------------------------------------------------------
# ESP — queries/esp.py serializers
# ---------------------------------------------------------------------------

_REGISTRY_ENTRY = SimpleNamespace(
    registry_id="espreg_1",
    canonical_key="ta.sma",
    package_entity_id="ent_1",
    trusted_active_revision_id="rev_1",
    trust_state=ResolverTrustState.TRUSTED_ACTIVE,
    runtime_adapter=RuntimeAdapter.PINE_V5,
    registry_version=4,
    replacement_revision_id=None,
)
_PACKAGE_ROOT = SimpleNamespace(visibility_scope=VisibilityScope.SYSTEM)


def test_esp_registry_entry_model_matches_the_registry_serializer() -> None:
    listed = esp_query._registry_dict(_REGISTRY_ENTRY, _PACKAGE_ROOT)
    nested = esp_query._registry_dict(_REGISTRY_ENTRY)
    # Both call sites are pinned against the MODEL, not against each other: comparing
    # the two to one another would hold for any single dict literal and prove nothing.
    assert set(listed) == _fields(esp_schema.EspRegistryEntry)
    assert set(nested) == _fields(esp_schema.EspRegistryEntry)
    # The nested call only NULLS `visibility_scope`; it never drops the key.
    assert nested["visibility_scope"] is None
    assert listed["visibility_scope"] == "system"


def test_esp_resolver_contract_model_matches_the_contract_serializer() -> None:
    contract = SimpleNamespace(
        contract_id="espc_1",
        canonical_key="ta.sma",
        signature={"params": ["src", "len"], "return": "series"},
        runtime_adapter=RuntimeAdapter.PINE_V5,
        warm_up_period=14,
        timing_semantics="bar_close",
        repaint=False,
        evidence=None,
    )
    assert set(esp_query._contract_dict(contract)) == _fields(esp_schema.EspResolverContract)


def test_esp_validation_run_model_matches_the_run_serializer() -> None:
    run = SimpleNamespace(
        run_id="espvr_1",
        status=PackageValidationState.PASSED,
        validator_version="esp-validation-v1",
        vectors_run=3,
        checks={"validator_version": "esp-validation-v1", "status": "passed", "checks": []},
        completed_at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
    )
    serialized = esp_query._validation_run_dict(run)
    assert serialized is not None
    assert set(serialized) == _fields(esp_schema.EspValidationRunSummary)
    # The stored envelope is an OPEN DICT here; the validate command's same-named field is
    # a LIST of checks. The two must not be merged — and the assertion has to name the
    # exact annotation, because `is not list` would also pass for `list[EspValidationCheck]`,
    # i.e. for precisely the merge this pins against.
    assert esp_schema.EspValidationRunSummary.model_fields["checks"].annotation == dict[str, Any]
    assert (
        esp_schema.EspValidationRunResponse.model_fields["checks"].annotation
        == list[esp_schema.EspValidationCheck]
    )


def test_esp_validation_check_model_matches_the_domain_check() -> None:
    check = ResolverCheck(name="contract_schema", status=PackageValidationState.PASSED, detail="ok")
    assert set(check.as_dict()) == _fields(esp_schema.EspValidationCheck)


def test_esp_detail_model_declares_every_projected_key() -> None:
    # get_esp_detail is DB-bound, so its literal is pinned here; the integration suite
    # drives the real endpoint.
    projected = {
        "entity_id",
        "revision_id",
        "revision_no",
        "package_kind",
        "visibility_scope",
        "validation_state",
        "approval_state",
        "content_hash",
        "row_version",
        "lifecycle_state",
        "owner_principal_id",
        "contract",
        "registry",
        "latest_validation_run",
        "created_at",
        "net_profit",
        "backtest_ready",
        "oos_passed",
    }
    assert _fields(esp_schema.EspPackageDetailResponse) == projected


# ---------------------------------------------------------------------------
# Library — queries/library.py serializers
# ---------------------------------------------------------------------------

_ACTOR = Actor(principal_id="prn_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


def _package_row() -> dict[str, Any]:
    root = SimpleNamespace(
        entity_id="ent_1",
        owner_principal_id="prn_1",
        lifecycle_state="active",
        row_version=3,
    )
    detail = SimpleNamespace(
        package_kind=PackageKind.STRATEGY,
        visibility_scope=VisibilityScope.PRIVATE,
        derived_from_revision_id=None,
    )
    revision = SimpleNamespace(
        revision_id="rev_1",
        revision_no=2,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
        content_hash="a" * 64,
        created_at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
        input_contract={"name": "Momentum", "market": "btcusdt", "timeframe": "15m"},
        output_contract={"output_kinds": ["signal"]},
        rationale_family_snapshot={"rationale_family_id": "rf_1", "display_name": "Momentum"},
    )
    return library_query._package_row(_ACTOR, root, detail, revision)


def test_library_row_model_matches_the_row_serializer() -> None:
    assert set(_package_row()) == _fields(library_schema.LibraryPackageRow)


def test_library_detail_model_is_a_strict_superset_of_the_row() -> None:
    row_fields = _fields(library_schema.LibraryPackageRow)
    detail_fields = _fields(library_schema.LibraryPackageDetailResponse)
    assert row_fields <= detail_fields
    # The seven keys get_package_detail appends on top of the row (it also OVERWRITES
    # `rationale_family` in place, which is why that one is not in this set).
    assert detail_fields - row_fields == {
        "input_contract",
        "output_contract",
        "dependency_snapshot",
        "validation_summary",
        "change_note",
        "provenance",
        "revisions",
    }
    # `rationale_family` is present on BOTH but is a WIDER shape on the detail. Naming the
    # two annotations exactly is the point: an `is not` identity check would still pass if
    # the detail model quietly LOST `pinned_name`/`family_active`.
    assert (
        library_schema.LibraryPackageRow.model_fields["rationale_family"].annotation
        == library_schema.PinnedRationaleFamilyRef | None
    )
    assert (
        library_schema.LibraryPackageDetailResponse.model_fields["rationale_family"].annotation
        == library_schema.LiveRationaleFamilyRef | None
    )
    assert _fields(library_schema.PinnedRationaleFamilyRef) < _fields(
        library_schema.LiveRationaleFamilyRef
    )


def test_permission_flags_model_matches_the_permissions_dataclass() -> None:
    # A dropped flag silently HIDES a UI action instead of failing loudly, so this is
    # pinned against the dataclass rather than a hand-written list.
    dataclass_fields = {f.name for f in dataclasses.fields(PackagePermissions)}
    assert dataclass_fields == _fields(library_schema.PackagePermissionFlags)
    # Every flag is a real bool on a real projection, not just a declared field.
    assert all(isinstance(v, bool) for v in _package_row()["permissions"].values())


def test_performance_stays_an_open_map_so_a_new_metric_cannot_be_dropped() -> None:
    performance = _package_row()["performance"]
    # A frozen literal, NOT `set(_PERFORMANCE_FIELDS)` — comparing `_performance_na()` to the
    # constant it is built from holds for any rename. These six names are the wire contract
    # the client index-reads (`frontend/src/lib/library.ts::PERFORMANCE_FIELDS`).
    assert set(performance) == {
        "net_profit",
        "max_drawdown",
        "romad",
        "win_rate",
        "trade_count",
        "out_of_sample",
    }
    # Never a fabricated zero (doc 08 §3.2, L4).
    assert all(value == "not_applicable" for value in performance.values())
    assert library_schema.LibraryPackageRow.model_fields["performance"].annotation == dict[str, str]


def test_pinned_family_model_matches_the_pinned_serializer() -> None:
    pinned = library_query._pinned_family({"rationale_family_id": "rf_1", "display_name": "Mom"})
    assert pinned is not None
    assert set(pinned) == _fields(library_schema.PinnedRationaleFamilyRef)
    assert library_query._pinned_family({}) is None


def test_a_poisoned_family_snapshot_cannot_break_the_typed_projection() -> None:
    """``rationale_family_snapshot`` is JSONB and ``POST /package-imports`` writes a
    caller-supplied manifest into it behind a container-level ``isinstance(dict)`` guard only
    (``jobs/package_import.py``). Before the typed contract a non-string id/name rendered as
    garbage; under ``response_model`` it would be a 500 on the whole catalog PAGE, for every
    viewer of that row. A non-string id is not a family reference, and ``42`` is not a name."""
    assert library_query._pinned_family({"rationale_family_id": 7, "display_name": 42}) is None
    assert library_query._pinned_family({"rationale_family_id": ["rf_1"]}) is None
    assert library_query._pinned_family({"rationale_family_id": ""}) is None

    named = library_query._pinned_family({"rationale_family_id": "rf_1", "display_name": 42})
    assert named == {"id": "rf_1", "name": None}

    # Whatever survives the guards satisfies the published model — that is the invariant.
    for snapshot in (
        {"rationale_family_id": "rf_1", "display_name": "Momentum"},
        {"rationale_family_id": "rf_1", "display_name": 42},
        {"rationale_family_id": "rf_1"},
    ):
        projected = library_query._pinned_family(snapshot)
        assert projected is not None
        library_schema.PinnedRationaleFamilyRef.model_validate(projected)


async def test_the_detail_family_projection_screens_the_same_poison() -> None:
    """``_live_family`` must reject a non-string id BEFORE it reaches the repository — the
    id is used as a lookup key, so an int would also be handed to SQL. The guard runs first,
    which is why ``None`` is a safe session here."""
    assert await library_query._live_family(None, {"rationale_family_id": 7}) is None
    assert await library_query._live_family(None, {"rationale_family_id": {"a": 1}}) is None
    assert await library_query._live_family(None, None) is None
    assert await library_query._live_family(None, {}) is None


def test_provenance_scan_model_matches_the_scan_serializer() -> None:
    scan = SimpleNamespace(
        scan_id="scan_1",
        attempt_no=1,
        status="passed",
        detected_calls=["ta.sma"],
        resolved_refs=[{"key": "ta.sma"}],
        missing_calls=[],
        unsupported_calls=[],
        registry_fingerprint="f" * 16,
        context_hash="c" * 16,
    )
    serialized = library_query._scan_summary(scan)
    assert serialized is not None
    assert set(serialized) == _fields(library_schema.PackageProvenanceScan)
    assert library_query._scan_summary(None) is None


def test_registry_observation_model_matches_the_export_builder() -> None:
    observation = build_registry_observation(_REGISTRY_ENTRY, exported_revision_id="rev_1")
    assert observation is not None
    assert set(observation) == _fields(library_schema.PackageRegistryObservation)
    assert observation["is_trusted_active_revision"] is True
    assert build_registry_observation(None, exported_revision_id="rev_1") is None


# ---------------------------------------------------------------------------
# Agent Tool Gateway — queries/agent_tool_gateway.py serializers
# ---------------------------------------------------------------------------


def _tool_call() -> SimpleNamespace:
    return SimpleNamespace(
        tool_call_id="agttool_1",
        tool_name="strategy.save_revision",
        task_id="agttask_1",
        checkpoint_id=None,
        actor_kind="agent",
        policy_scope="proposal",
        status="succeeded",
        artifact_output_ref=None,
        failure_code=None,
        failure_message=None,
        correlation_id="corr_1",
        created_at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 3, 12, 1, tzinfo=UTC),
        agent_id="alpha",
        actor_principal_id="prn_agent",
        input_manifest_id=None,
        idempotency_key="k-1",
        request={"display_name": "Momentum"},
        response_ref={"strategy_root_id": "sr_1", "revision_number": 2},
    )


def test_tool_call_card_model_matches_the_card_serializer() -> None:
    assert set(tg_query._tool_call_card(_tool_call())) == _fields(tg_schema.AgentToolCallCard)


def test_tool_call_detail_model_matches_the_detail_serializer() -> None:
    detail = tg_query._tool_call_detail(_tool_call())
    assert set(detail) == _fields(tg_schema.AgentToolCallDetailResponse)
    # The detail is the card plus exactly six payload/provenance keys.
    card_fields = _fields(tg_schema.AgentToolCallCard)
    assert card_fields <= _fields(tg_schema.AgentToolCallDetailResponse)
    assert _fields(tg_schema.AgentToolCallDetailResponse) - card_fields == {
        "agent_id",
        "actor_principal_id",
        "input_manifest_id",
        "idempotency_key",
        "request",
        "response_ref",
    }


def test_tool_call_payloads_stay_open_so_no_tool_result_is_dropped() -> None:
    # `response_ref` is discriminated by `tool_name` across the whole registry and stores
    # the backing command's return VERBATIM (Strategy / Trading Signal parity slices
    # included). A closed union would drop fields from every tool it did not yet know.
    detail_fields = tg_schema.AgentToolCallDetailResponse.model_fields
    assert detail_fields["request"].annotation == dict[str, Any]
    assert detail_fields["response_ref"].annotation == (dict[str, Any] | None)
