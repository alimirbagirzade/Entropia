"""G-02 — the ESP export artifact contract, schema v2 (doc 08 §7/§9.1, doc 09 §14/§15).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

Doc 09 **ESP-19**: "User exports exact ESP revision -> artifact contains root/revision
identity, content hash, signature, adapter ref, evidence and dependency manifest."
Schema v1 shipped identity + content hash + dependency manifest; the adapter ref, the
timing/repaint semantics and the validation evidence live on ``embedded_resolver_contract``
/ ``embedded_resolver_validation_run`` and were absent, so an exported ESP could not state
which runtime semantics had certified it (``docs/audit`` G-02).

What this file pins, and why each one is a separate risk:

* the four v2 fields are present and read from the EXPORTED revision's own rows;
* the hash is deterministic — two exports minutes apart, and an export taken AFTER the
  registry moved, all produce the same digest, because no export-time clock and no live
  registry state is inside the artifact;
* an old revision is never re-read through the current head;
* absent evidence is reported as ``legacy_incomplete_evidence``, never as a pass — this is
  the failure mode that would matter most, since a fabricated pass is worse than no export;
* tampering with any hashed field is detectable by recomputation;
* the live registry pointer rides the ENVELOPE, and its answer may change while the
  artifact's hash does not;
* a non-ESP export gains the version fields and fabricates nothing else.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import esp as esp_cmd
from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.export_contract import (
    EVIDENCE_LEGACY_INCOMPLETE,
    EVIDENCE_RECORDED,
    EXPORT_SCHEMA_VERSION,
    EXPORTER_VERSION,
)
from entropia.infrastructure.postgres.models import AuditEvent
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import idempotency as idem_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.idempotency import request_fingerprint
from entropia.shared.manifest import manifest_hash

from .test_acceptance_esp_package_gaps import (
    _SMA_SIG,
    ADMIN,
    OWNER,
    _create_esp,
    _seed_principals,
    _trusted_esp,
)

pytestmark = pytest.mark.integration


# The v1 manifest key set, frozen here as the compatibility reference. v2 must ADD to this
# and never rename or drop a member — a v1 reader that loses a key it depends on is a break
# no version field can excuse.
_V1_MANIFEST_KEYS = frozenset(
    {
        "package_root_id",
        "revision_id",
        "revision_no",
        "package_kind",
        "name",
        "input_contract",
        "output_contract",
        "dependency_snapshot",
        "rationale_family_snapshot",
        "validation_state",
        "approval_state",
        "content_hash",
        "derived_from_revision_id",
    }
)


async def _export(session, esp: dict, *, idempotency_key: str | None = None) -> dict:
    return await pkg_cmd.export_package(
        session,
        ADMIN,
        entity_id=esp["entity_id"],
        revision_id=esp["revision_id"],
        idempotency_key=idempotency_key,
    )


# --------------------------------------------------------------------------- #
# ESP-19 — the v2 artifact carries the full resolver contract + evidence        #
# --------------------------------------------------------------------------- #


async def test_esp_export_v2_carries_contract_adapter_and_validation_evidence(session) -> None:
    """ESP-19, in full: every fact doc 09 §15 names is IN the artifact.

    v1 could only satisfy the identity/hash/dependency half of that sentence. Each
    assertion below is compared against the DATABASE row rather than a literal, so the
    test proves the artifact mirrors the certified contract and not a hand-copied echo."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    contract = await esp_repo.get_contract_by_revision(session, esp["revision_id"])
    run = await esp_repo.get_latest_validation_run(session, esp["revision_id"])
    assert contract is not None and run is not None

    manifest = (await _export(session, esp))["manifest"]

    assert manifest["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert manifest["exporter_version"] == EXPORTER_VERSION

    snapshot = manifest["resolver_contract_snapshot"]
    assert snapshot["contract_id"] == contract.contract_id
    assert snapshot["revision_id"] == esp["revision_id"]
    assert snapshot["canonical_key"] == "ta.sma"
    assert snapshot["signature"] == _SMA_SIG
    assert snapshot["runtime_adapter"] == str(RuntimeAdapter.PINE_V5)
    assert snapshot["repaint"] is False
    assert snapshot["warm_up_period"] == contract.warm_up_period
    assert snapshot["timing_semantics"] == contract.timing_semantics
    assert snapshot["evidence"] == contract.evidence
    # A row-birth timestamp is not a contract fact and would not survive a re-export of a
    # re-seeded environment — it is deliberately absent (see export_contract.py note 1).
    assert "created_at" not in snapshot

    evidence = manifest["validation_evidence_snapshot"]
    assert evidence["evidence_state"] == EVIDENCE_RECORDED
    assert evidence["validation_run_id"] == run.run_id
    assert evidence["validator_version"] == run.validator_version
    assert evidence["status"] == str(PackageValidationState.PASSED)
    assert evidence["vectors_run"] == run.vectors_run == 1
    assert evidence["checks"] == run.checks
    assert evidence["completed_at"] is not None

    # The v1 half of ESP-19 must still hold — this slice adds, it does not displace.
    revision = await pkg_repo.get_revision(session, esp["revision_id"])
    assert revision is not None
    assert manifest["package_root_id"] == esp["entity_id"]
    assert manifest["package_kind"] == str(PackageKind.EMBEDDED_SYSTEM)
    assert manifest["content_hash"] == revision.content_hash
    assert "dependency_snapshot" in manifest


async def test_export_audit_metadata_records_the_schema_and_exporter_version(session) -> None:
    """The ``package.exported`` audit says WHICH artifact shape its hash covers.

    Without the version, a stored provenance hash is unfalsifiable later: two shapes of the
    same revision hash differently and nothing on the row would say which one was taken."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    exported = await _export(session, esp)
    await session.flush()

    row = (
        await session.execute(select(AuditEvent).where(AuditEvent.event_kind == "package.exported"))
    ).scalar_one()
    assert row.event_metadata["manifest_hash"] == exported["manifest_hash"]
    assert row.event_metadata["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert row.event_metadata["exporter_version"] == EXPORTER_VERSION


# --------------------------------------------------------------------------- #
# Determinism, tamper detection, idempotent replay                              #
# --------------------------------------------------------------------------- #


async def test_same_immutable_input_hashes_identically_across_separate_exports(session) -> None:
    """Two independent exports (distinct idempotency keys) of one revision agree.

    A replay-cache hit would prove nothing, so the two exports use DIFFERENT keys and must
    still agree byte-for-byte. The v2 payload is asserted to be INSIDE the hashed manifest
    first: a v1 export is trivially deterministic too, so without that check this test would
    keep passing with the whole slice reverted and would guard nothing."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    first = await _export(session, esp, idempotency_key="g02-det-a")
    await session.flush()
    second = await _export(session, esp, idempotency_key="g02-det-b")
    await session.flush()

    # The v2 facts are part of what is being hashed — not a sidecar.
    assert first["manifest"]["resolver_contract_snapshot"]["runtime_adapter"]
    assert first["manifest"]["validation_evidence_snapshot"]["validation_run_id"]
    assert first["manifest"] == second["manifest"]
    assert first["manifest_hash"] == second["manifest_hash"]
    # Recomputing the digest from the artifact alone reproduces it — the artifact is
    # self-verifying, with no server-side secret in the hash.
    assert manifest_hash(first["manifest"]) == first["manifest_hash"]


async def test_a_second_validation_run_produces_a_new_artifact_that_names_its_run(
    session,
) -> None:
    """Re-validating a revision legitimately changes the artifact — and says so.

    Documented boundary, not an accident. The evidence snapshot tracks the LATEST run
    because ``run_resolver_validation`` copies that run's status onto
    ``revision.validation_state``; pinning an older run could advertise ``passed`` on a
    revision the system now considers failed. What must hold is that the artifact is never
    AMBIGUOUS: ``validation_run_id`` names exactly which run backs this digest."""
    await _seed_principals(session)
    esp = await _create_esp(session)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=esp["entity_id"], revision_id=esp["revision_id"]
    )
    await session.commit()
    first = await _export(session, esp, idempotency_key="g02-reval-1")
    await session.commit()

    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=esp["entity_id"], revision_id=esp["revision_id"]
    )
    await session.commit()
    second = await _export(session, esp, idempotency_key="g02-reval-2")

    run_a = first["manifest"]["validation_evidence_snapshot"]["validation_run_id"]
    run_b = second["manifest"]["validation_evidence_snapshot"]["validation_run_id"]
    assert run_a != run_b
    assert first["manifest_hash"] != second["manifest_hash"]
    # The newest run is the one selected, and the repo's ordering is total so this is a
    # decision rather than a coin-flip between two same-transaction rows.
    latest = await esp_repo.get_latest_validation_run(session, esp["revision_id"])
    assert latest is not None and run_b == latest.run_id


async def test_an_approval_transition_produces_a_new_artifact_of_the_same_revision(
    session,
) -> None:
    """``approval_state`` is mutable in place, so it moves the digest — by design.

    Stated here because the alternative readings are both worse: dropping the field would
    make the artifact silent about whether the exported revision was ever approved, and
    claiming the digest is frozen for the life of the revision would simply be false."""
    await _seed_principals(session)
    esp = await _create_esp(session)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=esp["entity_id"], revision_id=esp["revision_id"]
    )
    await session.commit()
    before = await _export(session, esp, idempotency_key="g02-appr-1")
    await session.commit()
    assert before["manifest"]["approval_state"] == str(ApprovalState.DRAFT)

    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=esp["entity_id"],
        revision_id=esp["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
    )
    await session.commit()

    after = await _export(session, esp, idempotency_key="g02-appr-2")
    assert after["manifest"]["approval_state"] == str(ApprovalState.APPROVED)
    assert after["manifest"]["validation_evidence_snapshot"]["revision_approval_state"] == str(
        ApprovalState.APPROVED
    )
    assert after["manifest_hash"] != before["manifest_hash"]


async def test_the_hash_preimage_covers_the_contract_and_evidence_but_not_live_registry(
    session,
) -> None:
    """Which fields the digest actually commits to — the real design question.

    That mutating a dict changes its SHA-256 is a property of SHA-256, not of this code. The
    property worth pinning is the BOUNDARY: the resolver contract and the validation
    evidence are inside the preimage (so a holder of the recorded hash can detect a forged
    adapter or a forged pass), while the live registry observation is outside it (so registry
    drift does not invalidate a correctly-recorded hash).

    ``repaint`` is the chosen probe: it is the one contract fact whose silent flip would turn
    a look-ahead-unsafe resolver into an apparently safe one.

    **Honest boundary:** this is verification available to an external reader holding an
    independent copy of the digest. The system itself never re-checks a *submitted*
    ``manifest_hash`` — ``submit_package_import`` computes its own digest of whatever it was
    given and compares nothing, by design (import re-resolves locally instead of trusting)."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    exported = await _export(session, esp)

    forged_adapter = {
        **exported["manifest"],
        "resolver_contract_snapshot": {
            **exported["manifest"]["resolver_contract_snapshot"],
            "repaint": True,
        },
    }
    assert manifest_hash(forged_adapter) != exported["manifest_hash"]

    forged_pass = {
        **exported["manifest"],
        "validation_evidence_snapshot": {
            **exported["manifest"]["validation_evidence_snapshot"],
            "status": "passed",
            "validation_run_id": "espv_forged",
        },
    }
    assert manifest_hash(forged_pass) != exported["manifest_hash"]

    # The other side of the boundary: the registry observation is not in the preimage, so
    # appending it cannot be what the recorded digest covered.
    assert (
        manifest_hash(
            {**exported["manifest"], "registry_observation": exported["registry_observation"]}
        )
        != exported["manifest_hash"]
    )
    assert "registry_observation" not in exported["manifest"]


async def test_idempotent_replay_returns_the_same_v2_envelope(session) -> None:
    """One key, two calls: identical envelope and exactly one audit row."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    first = await _export(session, esp, idempotency_key="g02-replay")
    await session.flush()
    second = await _export(session, esp, idempotency_key="g02-replay")
    await session.flush()

    assert first == second
    assert second["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert second["manifest"]["resolver_contract_snapshot"]["canonical_key"] == "ta.sma"
    count = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_kind == "package.exported")
        )
    ).scalar_one()
    assert int(count) == 1


async def test_pre_v2_idempotency_replay_is_labelled_v1_and_never_rewrites_its_manifest(
    session,
) -> None:
    """A record written before G-02 replays as a v1 artifact, not a broken v2 one.

    Driven through the REAL replay path: a genuine ``idempotency_keys`` row is planted with
    the pre-slice four-key envelope and the exact fingerprint ``export_package`` computes,
    then the command is called with that key. ``run_idempotent`` short-circuits and returns
    the stored ``response_ref``, which is what the new typed ``PackageExportResponse`` must
    survive. Calling the private helper directly would have proved only that the helper works
    — not that the path it defends actually reaches it.

    O-30 discipline: the envelope gains truthful defaults (``export_schema_version = 1``, no
    registry observation) while the stored manifest is returned VERBATIM — back-filling a
    version field into it would invalidate the ``manifest_hash`` the audit already recorded,
    and would mutate a stored JSONB column in place."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    key = "g02-pre-v2-record"

    stored_manifest = {"package_root_id": esp["entity_id"], "revision_id": esp["revision_id"]}
    legacy_envelope = {
        "entity_id": esp["entity_id"],
        "revision_id": esp["revision_id"],
        "manifest_hash": "0" * 64,
        "manifest": stored_manifest,
    }
    row = idem_repo.add_key(
        session,
        key=key,
        actor_principal_id=ADMIN.principal_id,
        request_hash=request_fingerprint(
            {"op": "export", "entity_id": esp["entity_id"], "revision_id": esp["revision_id"]}
        ),
    )
    idem_repo.complete_key(row, response_ref=legacy_envelope)
    await session.flush()

    replayed = await _export(session, esp, idempotency_key=key)

    assert replayed["manifest_hash"] == "0" * 64  # the stored record, not a fresh export
    assert replayed["export_schema_version"] == 1
    assert replayed["registry_observation"] is None
    assert replayed["manifest"] == stored_manifest
    assert "export_schema_version" not in replayed["manifest"]
    # The stored response_ref JSONB is not mutated in place (O-30).
    stored = await idem_repo.get_key(session, key)
    assert stored is not None
    assert stored.response_ref is not None
    assert "export_schema_version" not in stored.response_ref
    assert "registry_observation" not in stored.response_ref


# --------------------------------------------------------------------------- #
# Historical fidelity — old revisions, moved heads, moved registry               #
# --------------------------------------------------------------------------- #


async def test_old_revision_export_is_not_reinterpreted_through_the_current_head(session) -> None:
    """Move the head, re-export the OLD revision: same artifact, same hash.

    The contract snapshot is keyed by the EXPORTED revision, so the newer head cannot leak
    into a historical artifact. The new head, which carries no resolver contract of its own,
    reports ``None`` rather than borrowing its predecessor's."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    before = await _export(session, esp, idempotency_key="g02-head-before")
    await session.flush()

    await pkg_cmd.create_package_revision(session, OWNER, entity_id=esp["entity_id"])
    await session.commit()
    root = await pkg_repo.get_package_root(session, esp["entity_id"])
    assert root is not None and root.current_revision_id != esp["revision_id"]

    after = await _export(session, esp, idempotency_key="g02-head-after")
    await session.flush()
    assert after["manifest"] == before["manifest"]
    assert after["manifest_hash"] == before["manifest_hash"]

    head_export = await pkg_cmd.export_package(
        session,
        ADMIN,
        entity_id=esp["entity_id"],
        revision_id=root.current_revision_id or "",
        idempotency_key="g02-head-new",
    )
    assert head_export["manifest"]["resolver_contract_snapshot"] is None
    assert head_export["manifest"]["validation_evidence_snapshot"] is None


async def test_registry_moves_but_the_immutable_artifact_does_not(session) -> None:
    """Deprecate the canonical key; the artifact's hash holds, the OBSERVATION changes.

    This is the whole reason live registry state is a sibling of the manifest rather than a
    member of it. A reader still learns that the key is no longer trusted-active — from the
    envelope, which is honest about being an observation made now."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    before = await _export(session, esp, idempotency_key="g02-reg-before")
    await session.flush()
    assert before["registry_observation"]["trust_state"] == str(ResolverTrustState.TRUSTED_ACTIVE)
    assert before["registry_observation"]["is_trusted_active_revision"] is True
    # Activation itself bumps the registry version, so a freshly trusted key reads 2.
    activated_version = before["registry_observation"]["registry_version"]
    # The live pointer is NOT part of the hashed artifact.
    assert "registry_observation" not in before["manifest"]

    await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key="ta.sma",
        reason="superseded by a newer resolver",
        expected_registry_version=activated_version,
    )
    await session.commit()

    after = await _export(session, esp, idempotency_key="g02-reg-after")
    await session.flush()

    assert after["manifest"] == before["manifest"]
    assert after["manifest_hash"] == before["manifest_hash"]
    assert after["registry_observation"]["trust_state"] == str(ResolverTrustState.DEPRECATED)
    assert after["registry_observation"]["registry_version"] == activated_version + 1


# --------------------------------------------------------------------------- #
# Absent evidence is reported as absent — never as a pass                        #
# --------------------------------------------------------------------------- #


async def test_esp_without_a_validation_run_reports_legacy_incomplete_evidence(session) -> None:
    """No run row -> ``legacy_incomplete_evidence`` with every run field ``None``."""
    await _seed_principals(session)
    esp = await _create_esp(session)  # created, never validated
    await session.commit()
    assert await esp_repo.get_latest_validation_run(session, esp["revision_id"]) is None

    manifest = (await _export(session, esp))["manifest"]
    evidence = manifest["validation_evidence_snapshot"]

    assert evidence["evidence_state"] == EVIDENCE_LEGACY_INCOMPLETE
    assert evidence["validation_run_id"] is None
    assert evidence["validator_version"] is None
    assert evidence["status"] is None
    assert evidence["vectors_run"] is None
    assert evidence["checks"] is None
    # The contract itself IS present — an unvalidated resolver still has a contract.
    assert manifest["resolver_contract_snapshot"]["canonical_key"] == "ta.sma"


async def test_a_passed_revision_with_no_run_row_still_refuses_to_claim_certified_evidence(
    session,
) -> None:
    """The dangerous legacy case: the revision reads PASSED but nothing certified it.

    A pre-R8 activation could leave ``validation_state = passed`` with no run row. The
    artifact must not launder that into validator-certified evidence: the revision's own
    state is reported, under its own name, while the evidence stays explicitly incomplete."""
    await _seed_principals(session)
    esp = await _create_esp(session)
    revision = await pkg_repo.get_revision(session, esp["revision_id"])
    assert revision is not None
    revision.validation_state = PackageValidationState.PASSED
    await session.commit()

    evidence = (await _export(session, esp))["manifest"]["validation_evidence_snapshot"]

    assert evidence["evidence_state"] == EVIDENCE_LEGACY_INCOMPLETE
    assert evidence["status"] is None  # NOT "passed" — no run said so
    assert evidence["revision_validation_state"] == str(PackageValidationState.PASSED)
    assert evidence["revision_approval_state"] == str(ApprovalState.DRAFT)


# --------------------------------------------------------------------------- #
# Non-ESP export is not disturbed                                               #
# --------------------------------------------------------------------------- #


async def test_non_esp_export_gains_only_the_version_fields_and_fabricates_nothing(
    session,
) -> None:
    """An INDICATOR package keeps its v1 body verbatim; the ESP snapshots are ``None``.

    ``None`` rather than an empty object: an empty contract stub would read as "a resolver
    contract exists and is blank", which is a different and false claim."""
    await _seed_principals(session)
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=OWNER.principal_id,
        created_by_principal_id=OWNER.principal_id,
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "Plain RSI"},
        output_contract={"output_kinds": ["directional_signal"]},
        dependency_snapshot={"resolved": [{"canonical_key": "ta.rsi"}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
    )
    await session.flush()

    manifest = (
        await pkg_cmd.export_package(
            session, OWNER, entity_id=root.entity_id, revision_id=revision.revision_id
        )
    )["manifest"]

    assert manifest["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert manifest["resolver_contract_snapshot"] is None
    assert manifest["validation_evidence_snapshot"] is None
    # "Only" means exactly these four keys beyond v1 — asserted as a set so a fifth
    # fabricated field cannot slip through the way a spot-check would let it.
    assert set(manifest) - _V1_MANIFEST_KEYS == {
        "export_schema_version",
        "exporter_version",
        "resolver_contract_snapshot",
        "validation_evidence_snapshot",
    }
    assert _V1_MANIFEST_KEYS - set(manifest) == set()
    # Every v1 field survives unchanged in name and value.
    assert manifest["name"] == "Plain RSI"
    assert manifest["package_kind"] == str(PackageKind.INDICATOR)
    assert manifest["content_hash"] == revision.content_hash
    assert manifest["dependency_snapshot"] == {"resolved": [{"canonical_key": "ta.rsi"}]}
