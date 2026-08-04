"""Package Library response contracts (doc 08 §3, §4, §7, §9.2).

Mirrors ``application/queries/library.py`` and ``application/commands/package_lifecycle.py``
key-for-key. ``PackageExportResponse`` and ``PackageValidationRunAcceptedResponse`` moved
here VERBATIM from ``routes/library.py`` — same class names, same fields, so the published
``components.schemas`` keys are unchanged — because the route module now imports a dozen
siblings and mixing two conventions would be worse than one move.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from entropia.apps.api.schemas.common import CursorPageMeta


class PackagePermissionFlags(BaseModel):
    """Server-computed action grants (``domain/package/permissions.py``).

    The UI early-returns on each flag, so a DROPPED flag silently hides the action instead
    of failing loudly — which is why the no-field-drop test pins this model against the
    backing dataclass's fields rather than a hand-written list."""

    can_view: bool
    can_use: bool
    can_derive: bool
    can_create_revision: bool
    can_request_validation: bool
    can_request_approval: bool
    can_approve_publish: bool
    can_deprecate: bool
    can_soft_delete: bool
    can_export: bool
    can_share: bool


class PinnedRationaleFamilyRef(BaseModel):
    """List-row family reference: the PINNED snapshot only (``_pinned_family``)."""

    id: str
    name: str | None


class LiveRationaleFamilyRef(BaseModel):
    """Detail family reference (``_live_family``) — strictly WIDER than the list row.

    The detail resolves the pinned snapshot to the family's CURRENT name (a rename without
    a re-pin) and reports whether the family is still active; a soft-deleted family keeps
    its pinned historical name and is flagged inactive. The two shapes are separate models
    on purpose: collapsing them would advertise ``pinned_name``/``family_active`` on list
    rows that never carry them."""

    id: str
    name: str | None
    pinned_name: str | None
    family_active: bool


class PackageProvenanceScan(BaseModel):
    """Dependency-scan evidence behind a Create-Package-built root (``_scan_summary``).

    ``resolved_refs`` / ``missing_calls`` / ``unsupported_calls`` are JSONB lists of
    per-call ROWS whose shape belongs to the Pre-Check plane, so they stay open."""

    scan_id: str
    attempt_no: int
    status: str
    detected_calls: list[str]
    resolved_refs: list[dict[str, Any]]
    missing_calls: list[dict[str, Any]]
    unsupported_calls: list[dict[str, Any]]
    registry_fingerprint: str
    context_hash: str


class PackageProvenance(BaseModel):
    """Best-effort Stage-2e creation provenance; ``null`` for a root with no request."""

    request_entity_id: str
    creation_mode: str
    source_kind: str
    source_language: str | None
    target_runtime: str
    draft_revision_id: str | None
    scan: PackageProvenanceScan | None


class PackageRevisionSummary(BaseModel):
    """One entry of the newest-first revision history (``_revision_history``, max 50)."""

    revision_id: str
    revision_no: int
    validation_state: str
    approval_state: str
    change_note: str | None
    created_at: str | None


class _LibraryPackageFields(BaseModel):
    """Every catalog field EXCEPT ``rationale_family`` (``queries/library.py::_package_row``).

    Split out so the list row and the detail can each declare their own family reference
    while the other nineteen fields are shared by construction — the frontend states the
    same rule as ``LibraryPackageDetail extends Omit<LibraryPackageRow, "rationale_family">``.
    Never used as a ``response_model``, so it is not published as its own schema component.

    ``lifecycle_state`` is nullable because ``entity_registry.lifecycle_state`` is a
    nullable free-form column, not an enum.

    ``performance`` stays an OPEN ``dict[str, str]`` rather than six named fields: the
    server sends ``"not_applicable"`` for every metric in this stage (no Strategy package
    has linked runs) and the client renders whatever string arrives by index. A closed
    model would silently drop a seventh metric the day one is added.

    ``market_scope`` / ``timeframe_scope`` are derived free strings, never an enum —
    ``derive_catalog_scope`` lowercases arbitrary contract content."""

    entity_id: str
    package_kind: str
    name: str | None
    current_revision_id: str
    revision_no: int
    lifecycle_state: str | None
    validation_state: str
    approval_state: str
    visibility_scope: str
    market_scope: str
    timeframe_scope: str
    output_kinds: list[str]
    derived_from_revision_id: str | None
    owner_principal_id: str | None
    row_version: int
    content_hash: str
    created_at: str | None
    permissions: PackagePermissionFlags
    performance: dict[str, str]


class LibraryPackageRow(_LibraryPackageFields):
    """One catalog row: the shared fields plus the PINNED family reference."""

    rationale_family: PinnedRationaleFamilyRef | None


class LibraryPageResponse(BaseModel):
    """``GET /library`` — cursor page of catalog rows."""

    data: list[LibraryPackageRow]
    meta: CursorPageMeta


class LibraryPackageDetailResponse(_LibraryPackageFields):
    """``GET /library/{entity_id}`` — the catalog row plus the full contracts.

    Extends the SHARED base rather than ``LibraryPackageRow`` so the detail can never fall
    out of superset with the list without overriding a field type (which mypy rejects as a
    Liskov violation). ``rationale_family`` is re-declared here as the live 4-field
    reference, exactly as the query overwrites that one key in place.

    The four contract blobs are caller-authored JSONB rendered verbatim by the UI and read
    by arbitrary key (``input_contract.market`` / ``.timeframe``), so they stay open."""

    input_contract: dict[str, Any]
    output_contract: dict[str, Any]
    dependency_snapshot: dict[str, Any] | None
    validation_summary: dict[str, Any] | None
    change_note: str | None
    rationale_family: LiveRationaleFamilyRef | None
    provenance: PackageProvenance | None
    revisions: list[PackageRevisionSummary]


class DeprecatePackageResponse(BaseModel):
    """``POST /library/{entity_id}/deprecate`` — ``active -> deprecated`` (doc 08 §7)."""

    entity_id: str
    lifecycle_state: str


class DerivePackageResponse(BaseModel):
    """``POST /library/{entity_id}/derive`` (201).

    ``entity_id`` is the NEW root the caller now owns; the path id is echoed back as
    ``source_entity_id``. Keeping both is what lets the UI navigate to the copy without
    re-reading the catalog, and the source is never mutated."""

    entity_id: str
    current_revision_id: str
    package_kind: str
    name: str
    derived_from_revision_id: str
    source_entity_id: str


class CreatePackageRevisionResponse(BaseModel):
    """``POST /library/{entity_id}/revisions`` (201).

    ``current_revision_id`` is read AFTER the append, so it equals the new ``revision_id``;
    ``base_revision_id`` is the head that was superseded. Both are reported because the
    OCC token for the NEXT call is the new head, while the audit trail needs the old one."""

    entity_id: str
    revision_id: str
    revision_no: int
    current_revision_id: str
    base_revision_id: str


class RequestPackageApprovalResponse(BaseModel):
    """``POST /library/{entity_id}/request-approval`` — ``draft -> approval_requested``."""

    entity_id: str
    revision_id: str
    approval_state: str


class ApprovePackageResponse(BaseModel):
    """``POST /library/{entity_id}/approve`` — Admin-only approve + publish in one tx.

    ``visibility_scope`` is NOT pinned to ``published``: the already-approved short-circuit
    branch echoes the row's live scope, which is whatever it actually holds."""

    entity_id: str
    revision_id: str
    approval_state: str
    visibility_scope: str


class PackageRegistryObservation(BaseModel):
    """LIVE ESP registry state read at export time (``build_registry_observation``).

    A SIBLING of the manifest, never a member: it is outside the hashed artifact so the
    answer to "is the revision in my hands still trusted-active?" can change while the
    ``manifest_hash`` does not."""

    canonical_key: str
    trust_state: str
    trusted_active_revision_id: str | None
    registry_version: int
    runtime_adapter: str
    is_trusted_active_revision: bool


class PackageExportResponse(BaseModel):
    """``POST /library/{entity_id}/export`` — the export envelope (G-02).

    A ``dict[str, Any]`` return kept this body invisible to ``docs/openapi.json`` while the
    drift guard stayed green — the same trap O-30 closed for the purge 202. ``manifest``
    stays an open object on purpose: it is a versioned, content-addressed artifact whose
    field set is stated by its own ``export_schema_version``, it is round-tripped verbatim
    into ``POST /package-imports``, and freezing it into a closed model here would make
    every future schema bump an API break.

    ``registry_observation`` is a SIBLING of the manifest, never a member (see
    ``domain/package/export_contract.py``). It is ``null`` for a package with no resolver
    contract, and ``null`` on a replay of a pre-G-02 idempotency record — but the key is
    always PRESENT, because ``_with_export_envelope_defaults`` back-fills a legacy envelope
    before it is returned. That is why it is required-and-nullable rather than optional."""

    entity_id: str
    revision_id: str
    manifest_hash: str
    export_schema_version: int
    manifest: dict[str, Any]
    registry_observation: PackageRegistryObservation | None


class PackageValidationRunAcceptedResponse(BaseModel):
    """``POST /library/{entity_id}/validation-runs`` (201) — the queued-validation envelope.

    The envelope deliberately names BOTH planes for one run. The caller addressed a package
    (``entity_id`` / ``revision_id``), but the evidence, the durable job and the state
    machine live in the CreatePackage plane (``request_id`` / ``validation_run_id`` /
    ``attempt_no`` / ``job_id``) — this route wraps that pipeline instead of owning a second
    one, so it reports the CP identifiers rather than minting Library-local ones.

    ``status`` and ``state`` answer DIFFERENT questions and are never collapsed: ``status``
    is the immutable run's ``ValidationRunStatus`` (``queued`` on admission), ``state`` is
    the request's ``CreatePackageState`` (``validation_running``). The terminal verdict
    lands on the projection when the durable worker finishes — this envelope only reports
    the admission."""

    entity_id: str
    revision_id: str
    request_id: str
    validation_run_id: str
    attempt_no: int
    status: str
    state: str
    job_id: str


__all__ = [
    "ApprovePackageResponse",
    "CreatePackageRevisionResponse",
    "DeprecatePackageResponse",
    "DerivePackageResponse",
    "LibraryPackageDetailResponse",
    "LibraryPackageRow",
    "LibraryPageResponse",
    "LiveRationaleFamilyRef",
    "PackageExportResponse",
    "PackagePermissionFlags",
    "PackageProvenance",
    "PackageProvenanceScan",
    "PackageRegistryObservation",
    "PackageRevisionSummary",
    "PackageValidationRunAcceptedResponse",
    "PinnedRationaleFamilyRef",
    "RequestPackageApprovalResponse",
]
