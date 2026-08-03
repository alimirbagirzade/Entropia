"""Package export artifact contract — schema v2 (G-02, doc 08 §7/§9.1, doc 09 §15 ESP-19).

Doc 09 **ESP-19** requires the export artifact to carry "root/revision identity, content
hash, signature, adapter ref, evidence and dependency manifest" and doc 09 §14 repeats it
("Exportu immutable revision, contract hash, adapter ref, test evidence manifest ve
dependencies uzerinden uret"). Schema v1 shipped identity + content hash + dependency
manifest only: the adapter ref, warm-up, timing/repaint semantics and the validation
evidence live on ``embedded_resolver_contract`` / ``embedded_resolver_validation_run``, so
an exported ESP could not say which runtime semantics it had been certified under.

This module is the PURE builder plane for the v2 artifact (no I/O, no session): the
application command loads the rows, these functions shape them.

**What the hash guarantees, stated precisely.** The manifest is a content-addressed snapshot
of ONE revision's certified state. Re-exporting with nothing changed in between reproduces
the digest exactly, because:

1. **No export-time clock.** Nothing here reads ``now()``. ``validation_run.completed_at`` IS
   hashed, but it is not an export-time stamp -- it is a column of the selected run row,
   frozen at that row's insert.
2. **No row-birth timestamps.** ``embedded_resolver_contract.created_at`` is deliberately NOT
   carried: it is a row-birth fact, not a contract fact, and doc 09 §15 does not ask for it.
   The contract row itself is genuinely immutable (UNIQUE on ``revision_id``, no writer
   mutates it), so ``resolver_contract_snapshot`` is stable for the life of the revision.
3. **Live state is not contract state.** The ESP registry pointer (trust state, registry
   version, trusted-active revision) moves independently of the exported revision, so it is
   NOT part of the manifest. :func:`build_registry_observation` shapes it as a SIBLING
   ``registry_observation`` on the response envelope: an observation made at export time,
   never a claim the artifact makes about itself. Activate a newer revision under the same
   canonical key and re-exporting the OLD revision still yields the OLD manifest_hash.

**What it does NOT guarantee, and must not be read as claiming.** Two facts the manifest
carries are genuinely mutable, so a re-export after either moves is a DIFFERENT artifact of
the same revision -- correctly so, and the artifact says which one it is:

* ``package_revision.validation_state`` / ``approval_state`` are updated in place as the
  revision progresses (``commands/esp.py`` on validate + activate,
  ``commands/package_lifecycle.py`` on request-approval + approve). An export taken before
  approval and one taken after legitimately differ.
* ``embedded_resolver_validation_run`` is append-only and a revision may be re-validated, so
  the evidence snapshot tracks the LATEST run. Latest -- not first -- is the only honest
  choice: ``run_resolver_validation`` copies the newest run's status onto
  ``revision.validation_state``, so pinning an older run could advertise ``passed`` on a
  revision the system now considers failed. ``validation_run_id`` names the exact run, so no
  artifact is ever ambiguous about which evidence backs it.

Both are pinned by tests in ``tests/integration/test_esp_export_contract_v2.py`` as intended
behaviour rather than left to be rediscovered as a surprise.

Because the observation is not in the manifest, it also never travels to a foreign system
on import: the importer must re-resolve against its OWN registry and a foreign adapter is
never auto-trusted (doc 08 §10, §14).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

# Bumping this changes the artifact SHAPE (like ENGINE_VERSION for the engine): a v1
# artifact and a v2 artifact of the same revision are different artifacts with different
# hashes, and the field says which one the reader is holding. Hashes are never compared
# across versions.
EXPORT_SCHEMA_VERSION = 2

# The producing code's identity, separate from the shape. Two exporters may emit the same
# schema version; this names which one actually wrote the bytes.
EXPORTER_VERSION = "entropia-package-exporter-v2"

# A manifest with NO ``export_schema_version`` predates the field and is a v1 artifact.
LEGACY_EXPORT_SCHEMA_VERSION = 1

# Import reads v1 and v2. Anything else -- a future version this build cannot interpret --
# is rejected fail-closed rather than parsed on a guess (doc 08 §10: an import that cannot
# be understood never becomes a silently executable package).
SUPPORTED_IMPORT_SCHEMA_VERSIONS = frozenset({LEGACY_EXPORT_SCHEMA_VERSION, EXPORT_SCHEMA_VERSION})

# ``validation_evidence_snapshot.evidence_state`` values.
EVIDENCE_RECORDED = "recorded"
# Doc 09 §7: "a successful one-off sample is not sufficient evidence for activation." A
# revision certified before the validation-run plane existed (or by a path that wrote no
# run row) has NO run to pin. The snapshot says so in these words and reports the
# revision's own states separately -- it never advertises ``passed`` on absent evidence.
EVIDENCE_LEGACY_INCOMPLETE = "legacy_incomplete_evidence"


class _ResolverContractRow(Protocol):
    """The immutable ``embedded_resolver_contract`` columns the artifact carries."""

    contract_id: str
    entity_id: str
    revision_id: str
    canonical_key: str
    signature: dict[str, Any]
    warm_up_period: int | None
    timing_semantics: str | None
    repaint: bool
    evidence: dict[str, Any] | None

    @property
    def runtime_adapter(self) -> Any: ...


class _ValidationRunRow(Protocol):
    """The immutable ``embedded_resolver_validation_run`` columns the artifact carries."""

    run_id: str
    validator_version: str
    vectors_run: int
    checks: dict[str, Any]
    completed_at: datetime | None

    @property
    def status(self) -> Any: ...


class _RegistryRow(Protocol):
    """The LIVE ``embedded_resolver_registry`` pointer -- observation only, never hashed."""

    canonical_key: str
    trusted_active_revision_id: str | None
    registry_version: int

    @property
    def trust_state(self) -> Any: ...

    @property
    def runtime_adapter(self) -> Any: ...


def build_resolver_contract_snapshot(
    contract: _ResolverContractRow | None,
) -> dict[str, Any] | None:
    """The immutable resolver contract facts ESP-19 requires, or ``None``.

    ``None`` means "this revision has no resolver contract" -- a non-ESP package, or an ESP
    revision predating its contract row. It is never an empty stub: an absent contract is
    reported as absent, not as a contract with blank semantics."""
    if contract is None:
        return None
    return {
        "contract_id": contract.contract_id,
        "package_root_id": contract.entity_id,
        "revision_id": contract.revision_id,
        "canonical_key": contract.canonical_key,
        "signature": contract.signature,
        "runtime_adapter": str(contract.runtime_adapter),
        "warm_up_period": contract.warm_up_period,
        "timing_semantics": contract.timing_semantics,
        "repaint": contract.repaint,
        "evidence": contract.evidence,
    }


def build_validation_evidence_snapshot(
    run: _ValidationRunRow | None,
    *,
    revision_validation_state: str,
    revision_approval_state: str,
) -> dict[str, Any]:
    """The validation-run evidence backing the exported revision.

    The revision's OWN ``validation_state`` / ``approval_state`` are always reported, and
    always separately from the run: a revision may read ``passed`` while no run row exists
    (a legacy activation), and collapsing the two would let the artifact claim
    validator-certified evidence it does not hold. When there is no run the snapshot is
    ``evidence_state = legacy_incomplete_evidence`` with every run field ``None`` -- an
    explicitly incomplete artifact, never a fabricated pass."""
    if run is None:
        return {
            "evidence_state": EVIDENCE_LEGACY_INCOMPLETE,
            "validation_run_id": None,
            "validator_version": None,
            "status": None,
            "vectors_run": None,
            "checks": None,
            "completed_at": None,
            "revision_validation_state": revision_validation_state,
            "revision_approval_state": revision_approval_state,
        }
    return {
        "evidence_state": EVIDENCE_RECORDED,
        "validation_run_id": run.run_id,
        "validator_version": run.validator_version,
        "status": str(run.status),
        "vectors_run": run.vectors_run,
        "checks": run.checks,
        # A column of the selected run row, frozen at that row's insert -- never an
        # export-time stamp. Selecting a DIFFERENT run (a re-validation) legitimately
        # changes it; see the module note on what the hash does and does not guarantee.
        "completed_at": run.completed_at.isoformat() if run.completed_at is not None else None,
        "revision_validation_state": revision_validation_state,
        "revision_approval_state": revision_approval_state,
    }


def build_registry_observation(
    entry: _RegistryRow | None, *, exported_revision_id: str
) -> dict[str, Any] | None:
    """The LIVE registry pointer observed at export time -- envelope only, never hashed.

    ``is_trusted_active_revision`` answers the one question a reader of an old export
    actually has: is the revision in my hands still the trusted-active one for this key?
    Reporting it here rather than inside the manifest is what lets the answer change
    while the artifact's hash does not."""
    if entry is None:
        return None
    return {
        "canonical_key": entry.canonical_key,
        "trust_state": str(entry.trust_state),
        "trusted_active_revision_id": entry.trusted_active_revision_id,
        "registry_version": entry.registry_version,
        "runtime_adapter": str(entry.runtime_adapter),
        "is_trusted_active_revision": entry.trusted_active_revision_id == exported_revision_id,
    }


def resolve_import_schema_version(manifest: Mapping[str, Any]) -> int | None:
    """The schema version an incoming manifest may be parsed as, or ``None`` to reject.

    Absent -- or an explicit ``null``, which states no version just as an absent key does --
    -> ``1``, so a v1 manifest still imports. ``1`` / ``2`` (int, or a digit string for a
    hand-pasted manifest) -> that version. Anything else -- a future version, a non-numeric
    label, a bool -- returns ``None`` so the caller fails closed. Accepting an unknown
    version would mean guessing at fields this build has never seen."""
    raw = manifest.get("export_schema_version")
    if raw is None:
        return LEGACY_EXPORT_SCHEMA_VERSION
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int) and raw in SUPPORTED_IMPORT_SCHEMA_VERSIONS:
        return raw
    if isinstance(raw, str) and raw.isdigit() and int(raw) in SUPPORTED_IMPORT_SCHEMA_VERSIONS:
        return int(raw)
    return None


def describe_origin_resolver_contract(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    """What a manifest CLAIMS about its resolver contract, marked untrusted.

    Gated on the KEY being present, not on the declared version: a manifest that carries a
    ``resolver_contract_snapshot`` is echoed whatever version it claims to be, because the
    echo is a report of what was submitted and reporting it is never less safe than staying
    silent about it. In practice only v2 exports write the key.

    The import worker re-resolves every dependency against the LOCAL registry (doc 08 §10);
    a foreign manifest's adapter/evidence is a claim about the exporting system, not a
    grant of trust here. This echo exists so the import report can SHOW the origin claim,
    and it carries the refusal with it -- ``trusted: False``. It is never written to
    ``embedded_resolver_contract`` and never seeds a registry pointer."""
    snapshot = manifest.get("resolver_contract_snapshot")
    if not isinstance(snapshot, dict):
        return None
    evidence = manifest.get("validation_evidence_snapshot")
    evidence = evidence if isinstance(evidence, dict) else {}
    return {
        "canonical_key": snapshot.get("canonical_key"),
        "runtime_adapter": snapshot.get("runtime_adapter"),
        "warm_up_period": snapshot.get("warm_up_period"),
        "timing_semantics": snapshot.get("timing_semantics"),
        "repaint": snapshot.get("repaint"),
        "origin_evidence_state": evidence.get("evidence_state"),
        "origin_validator_version": evidence.get("validator_version"),
        "origin_validation_status": evidence.get("status"),
        # The two refusals, stated on the record the report renders.
        "trusted": False,
        "local_revalidation_required": True,
    }


__all__ = [
    "EVIDENCE_LEGACY_INCOMPLETE",
    "EVIDENCE_RECORDED",
    "EXPORTER_VERSION",
    "EXPORT_SCHEMA_VERSION",
    "LEGACY_EXPORT_SCHEMA_VERSION",
    "SUPPORTED_IMPORT_SCHEMA_VERSIONS",
    "build_registry_observation",
    "build_resolver_contract_snapshot",
    "build_validation_evidence_snapshot",
    "describe_origin_resolver_contract",
    "resolve_import_schema_version",
]
