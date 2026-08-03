"""I-17-COV — acceptance-ID coverage gaps on the ESP / package line.

Auto-skips without PostgreSQL (see tests/integration/conftest.py). Every test here
closes an acceptance ID that ``docs/audit/acceptance_id_map.md`` §E listed as a
GENUINE coverage gap (no test, not merely no tag):

- PC-14 (doc 07 §NN): a non-Admin resolver approval is a typed 403 and the
  proposal/draft survives untouched — registry pointer, registry_version,
  revision approval state and the approval-decision table are all unchanged.
- PC-19 (doc 07): soft-deleting an ESP that a historical package revision pinned
  leaves that historical dependency manifest readable and reproducible.
- ESP-19 (docs/audit, doc 09 row 19): exporting an exact ESP revision yields an
  artifact carrying root/revision identity, content hash and dependency manifest.
- RF-15 (doc 10 §14) / ESP-05 (docs/audit, doc 09 row 5): the V18 seed Family
  ``Embedded System / TA Resolver`` is seeded ACTIVE under exactly that string and
  an ESP package pinning it is returned by the catalog's rationale-family filter —
  the id-based relation V18's string mismatch broke.
- PL-06 (docs/audit, doc 08 row 6): a Condition package's ROMAD (and every sibling
  performance metric) is reported ``not_applicable``, never a fabricated zero, and
  the catalog query exposes no sort parameter at all — so nothing can rank on it.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import esp as esp_cmd
from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.commands.deletion import soft_delete_entity
from entropia.application.queries import library as library_query
from entropia.application.queries import rationale as rationale_query
from entropia.apps.seed import _seed_rationale_families
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.rationale import normalized_name
from entropia.infrastructure.postgres.models import (
    ApprovalDecision,
    Principal,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import ApprovalRequiresAdmin
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_SEED_FAMILY_NAME = "Embedded System / TA Resolver"

_SMA_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
# A real ta.sma(3) vector over [1..5] — the validation-run must PASS before an
# Admin may activate (R8), so every "trusted" fixture below goes through it.
_EVIDENCE = {
    "test_vectors": [
        {
            "name": "sma_len3",
            "length": 3,
            "close": [1, 2, 3, 4, 5],
            "expected": [None, None, 2, 3, 4],
        }
    ],
    "review": "passed",
}


class _NullLog:
    """The seed helpers log structured events; tests do not assert on them."""

    def info(self, *_args: Any, **_kwargs: Any) -> None:
        return None


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _create_esp(session, *, key: str = "ta.sma") -> dict:
    return await esp_cmd.create_esp_package(
        session,
        OWNER,
        canonical_key=key,
        signature=_SMA_SIG,
        runtime_adapter=RuntimeAdapter.PINE_V5,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        evidence=_EVIDENCE,
        visibility_scope=VisibilityScope.SYSTEM,
    )


async def _trusted_esp(session, *, key: str = "ta.sma") -> dict:
    """Create -> validate -> Admin-activate one resolver (the trusted fixture)."""
    created = await _create_esp(session, key=key)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=created["entity_id"], revision_id=created["revision_id"]
    )
    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key=key,
        expected_registry_version=1,
    )
    await session.commit()
    return created


# --------------------------------------------------------------------------- #
# PC-14 — resolver approval is Admin-only; the proposal survives the refusal    #
# --------------------------------------------------------------------------- #


async def test_user_resolver_approval_is_denied_and_the_proposal_stays_intact(session) -> None:
    """PC-14 (doc 07): "User tries resolver approval -> 403 ... proposal/draft
    remains intact." The typed denial is the FIRST half; the second half is that
    nothing moved — asserted field by field, because a partially-applied
    activation would be worse than an accepted one.

    Code name: doc 07 spells the refusal ``package_publish_admin_only``; the
    implementation ships ``APPROVAL_REQUIRES_ADMIN`` (a 403 ``ForbiddenError``).
    Under the O-03 convention the SHIPPED name wins — see
    ``docs/audit/acceptance_id_map.md`` §D.
    """
    await _seed_principals(session)
    created = await _create_esp(session)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=created["entity_id"], revision_id=created["revision_id"]
    )
    await session.commit()
    decisions_before = await _count(session, ApprovalDecision)

    with pytest.raises(ApprovalRequiresAdmin) as exc_info:
        await esp_cmd.activate_resolver(
            session,
            OWNER,  # the page's "User" role — never an Admin
            entity_id=created["entity_id"],
            revision_id=created["revision_id"],
            canonical_key="ta.sma",
            expected_registry_version=1,
        )
    await session.rollback()
    assert exc_info.value.code == "APPROVAL_REQUIRES_ADMIN"
    assert exc_info.value.http_status == 403

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.CANDIDATE
    assert entry.registry_version == 1
    assert entry.trusted_active_revision_id is None

    revision = await pkg_repo.get_revision(session, created["revision_id"])
    assert revision is not None
    # The PASSED validation the owner legitimately ran is untouched; only the
    # Admin-only APPROVAL is withheld.
    assert revision.validation_state == PackageValidationState.PASSED
    assert revision.approval_state != ApprovalState.APPROVED
    assert await _count(session, ApprovalDecision) == decisions_before


# --------------------------------------------------------------------------- #
# PC-19 — a historical pin survives the ESP's soft delete                       #
# --------------------------------------------------------------------------- #


async def test_soft_deleted_esp_keeps_the_historical_dependency_manifest_readable(session) -> None:
    """PC-19 (doc 07): "Soft delete an ESP that historical package revision
    referenced -> historical dependency manifest remains readable/reproducible."

    The dependent revision is immutable, so the assertion is that BOTH ends of the
    pin still read back: the snapshot on the dependent revision AND the exact ESP
    revision it names (same content hash) — the pair a historical manifest needs to
    reproduce the run.

    HOLE CLOSED (``fix/esp-lifecycle-resolution``). This docstring used to record
    that PC-19's SECOND clause — "new Pre-Check does not resolve
    soft-deleted/inactive ESP" — did NOT hold: soft delete left
    ``embedded_resolver_registry`` untouched and ``resolve_embedded_dependency``
    read only ``entry.trust_state``, so a probe that activated ``ta.sma``,
    soft-deleted its root and resolved it got the SAME trusted revision back.
    Resolution now also reads the root's ``deletion_state`` and ``lifecycle_state``,
    and a trusted-active resolver root cannot be deleted at all without deprecating
    first (doc 09 §9.5 step 2) — which is why the delete below is now two calls.
    Clause 2 lives in ``test_esp_lifecycle_resolution.py``; THIS test remains the
    clause-1 guard, so it keeps proving that closing a resolver for new work costs
    history nothing.
    """
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    esp_revision = await pkg_repo.get_revision(session, esp["revision_id"])
    assert esp_revision is not None
    pinned_hash = esp_revision.content_hash

    dependency_snapshot = {
        "resolved": [
            {
                "canonical_key": "ta.sma",
                "embedded_entity_id": esp["entity_id"],
                "embedded_revision_id": esp["revision_id"],
            }
        ]
    }
    dependent_root, _detail, dependent_revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "Uses ta.sma"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot=dependency_snapshot,
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.commit()

    # Deprecate-first is mandatory for a trusted-active resolver (ESP-17): a direct
    # delete is refused with DELETE_POLICY_BLOCKED, so the ordered path is used.
    await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key="ta.sma",
        reason="retired",
        expected_registry_version=2,
    )
    await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="retired")
    await session.commit()

    esp_root = await pkg_repo.get_package_root(session, esp["entity_id"])
    assert esp_root is not None and esp_root.deletion_state == DeletionState.SOFT_DELETED

    # The historical manifest still reads — snapshot verbatim, pinned revision alive.
    historical = await pkg_repo.get_revision(session, dependent_revision.revision_id)
    assert historical is not None
    assert historical.dependency_snapshot == dependency_snapshot
    still_pinned = await pkg_repo.get_revision(session, esp["revision_id"])
    assert still_pinned is not None
    assert still_pinned.content_hash == pinned_hash
    assert dependent_root.deletion_state == DeletionState.ACTIVE


# --------------------------------------------------------------------------- #
# ESP-19 — export artifact of an exact ESP revision                             #
# --------------------------------------------------------------------------- #


async def test_esp_revision_export_carries_identity_hash_and_dependency_manifest(session) -> None:
    """ESP-19 (docs/audit, doc 09 row 19): "User exports exact ESP revision ->
    artifact contains root/revision identity, content hash, signature, adapter ref,
    evidence and dependency manifest."

    PROVEN IN FULL as of G-02 (export schema v2). This row was previously PARTIAL: the
    adapter ref and the evidence live on ``embedded_resolver_contract`` /
    ``embedded_resolver_validation_run`` while the manifest was built from the package
    REVISION only, so the artifact carried identity + content hash + dependency manifest
    and nothing about the runtime semantics it had been certified under. The gap is closed;
    every clause of the sentence is asserted here.

    This test keeps the row's END-TO-END shape (create -> validate -> activate -> export).
    The contract's field-by-field fidelity, determinism, tamper detection and the
    absent-evidence behaviour live in ``test_esp_export_contract_v2.py``.
    """
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    exported = await pkg_cmd.export_package(
        session, ADMIN, entity_id=esp["entity_id"], revision_id=esp["revision_id"]
    )
    await session.commit()

    manifest = exported["manifest"]
    # identity
    assert manifest["package_root_id"] == esp["entity_id"]
    assert manifest["revision_id"] == esp["revision_id"]
    assert manifest["package_kind"] == str(PackageKind.EMBEDDED_SYSTEM)
    # content hash
    revision = await pkg_repo.get_revision(session, esp["revision_id"])
    assert revision is not None
    assert manifest["content_hash"] == revision.content_hash
    assert exported["manifest_hash"]
    # signature — now a first-class contract field, not only the input_contract echo
    assert manifest["input_contract"]["resolver_key"] == "ta.sma"
    contract_snapshot = manifest["resolver_contract_snapshot"]
    assert contract_snapshot["canonical_key"] == "ta.sma"
    assert contract_snapshot["signature"] == _SMA_SIG
    # adapter ref (+ the timing semantics that make it interpretable)
    assert contract_snapshot["runtime_adapter"] == str(RuntimeAdapter.PINE_V5)
    assert contract_snapshot["repaint"] is False
    # evidence
    evidence = manifest["validation_evidence_snapshot"]
    assert evidence["evidence_state"] == "recorded"
    assert evidence["status"] == str(PackageValidationState.PASSED)
    assert evidence["validator_version"]
    assert evidence["vectors_run"] == 1
    # dependency manifest
    assert "dependency_snapshot" in manifest


# --------------------------------------------------------------------------- #
# RF-15 / ESP-05 — the seed Family and the ESP relation that hangs off it       #
# --------------------------------------------------------------------------- #


async def test_seeded_ta_resolver_family_is_active_and_binds_esp_packages_by_id(session) -> None:
    """RF-15 (doc 10 §14) + ESP-05 (docs/audit, doc 09 row 5).

    V18's ESP metadata referenced the Family string ``Embedded System / TA
    Resolver`` while the prototype's card list omitted it — the "string mismatch"
    both rows forbid. Production seeds the Family ACTIVE (``apps/seed.py``
    ``_RATIONALE_FAMILIES`` last entry) and the ESP<->Family relation is carried by
    the family ID, not by the name. Both halves are asserted.
    """
    await _seed_principals(session)
    await _seed_rationale_families(session, _NullLog())
    await session.commit()

    families = await rationale_query.list_families(session, OWNER, PageParams(limit=50))
    by_name = {row["display_name"]: row for row in families["data"]}
    assert _SEED_FAMILY_NAME in by_name, "the V18 ESP Family is missing from the ACTIVE seed"
    seeded = by_name[_SEED_FAMILY_NAME]
    # Exact-string agreement is the whole point of RF-15: the normalized key the
    # lookup uses must be the normalization of the SAME string ESP metadata names.
    assert seeded["normalized_name"] == normalized_name(_SEED_FAMILY_NAME)
    assert "TA Resolver" in seeded["subfamilies"]

    family_id = seeded["entity_id"]
    await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"name": "ESP_TA_SMA", "resolver_key": "ta.sma"},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        rationale_family_snapshot={
            "rationale_family_id": family_id,
            "display_name": _SEED_FAMILY_NAME,
        },
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.commit()

    filtered = await library_query.list_packages(
        session,
        OWNER,
        PageParams(limit=50),
        filters=parse_catalog_filters(
            package_type=str(PackageKind.EMBEDDED_SYSTEM), rationale_family_id=family_id
        ),
    )
    rows = filtered["data"]
    assert [row["name"] for row in rows] == ["ESP_TA_SMA"]
    assert rows[0]["rationale_family"] == {"id": family_id, "name": _SEED_FAMILY_NAME}


# --------------------------------------------------------------------------- #
# PL-06 — metric applicability: N/A, never a fabricated zero, never sortable    #
# --------------------------------------------------------------------------- #


async def test_condition_package_romad_is_not_applicable_and_nothing_can_sort_on_it(
    session,
) -> None:
    """PL-06 (docs/audit, doc 08 row 6): "User sorts Condition Packages by ROMAD ->
    API/UI returns Not applicable / blocks sort for type scope; it does not rank
    fabricated zero values."

    Both clauses are provable today, in the strongest form the implementation
    offers: the row reports ``not_applicable`` for ROMAD (and every sibling
    metric), and the catalog query takes NO sort parameter at all — so there is no
    ranking surface a Condition row could be fabricated into.
    """
    await _seed_principals(session)
    await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.CONDITION,
        input_contract={"name": "Oversold gate"},
        output_contract={"output_kinds": ["condition"]},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
    )
    await session.commit()

    listed = await library_query.list_packages(
        session,
        OWNER,
        PageParams(limit=50),
        filters=parse_catalog_filters(package_type=str(PackageKind.CONDITION)),
    )
    assert len(listed["data"]) == 1
    performance = listed["data"][0]["performance"]
    assert performance["romad"] == "not_applicable"
    # Not one metric is a zero/None that a client could rank on.
    assert set(performance.values()) == {"not_applicable"}

    assert "sort" not in inspect.signature(library_query.list_packages).parameters
