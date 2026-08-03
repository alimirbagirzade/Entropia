"""Embedded System Package response contracts (doc 09 §8, §10.1, §11.1).

Mirrors ``application/queries/esp.py`` and ``application/commands/esp.py`` key-for-key.
The resolver *contract* payloads (``signature``, ``evidence``) and the stored validation
report (``latest_validation_run.checks``) stay OPEN objects on purpose: they are
version-namespaced JSONB artifacts (``validator_version``) whose field set is stated by the
artifact itself, so freezing them here would make every future validator bump an API break.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from entropia.apps.api.schemas.common import CursorPageMeta


class EspRegistryEntry(BaseModel):
    """One resolver registry row (``queries/esp.py::_registry_dict``).

    ``visibility_scope`` is nullable BY CONTEXT, not by accident: list rows carry the
    backing package root's scope, while the ``registry`` block nested inside the detail
    sends ``null`` rather than re-resolving a possibly-different package's root just to
    duplicate the detail's own top-level ``visibility_scope``.

    The performance triplet is the literal string ``"not_applicable"`` — resolvers have no
    runs, and a fabricated zero would read as a measured result (doc 09 §14, L4)."""

    registry_id: str
    canonical_key: str
    package_entity_id: str
    trusted_active_revision_id: str | None
    trust_state: str
    runtime_adapter: str
    registry_version: int
    replacement_revision_id: str | None
    visibility_scope: str | None
    net_profit: str
    backtest_ready: str
    oos_passed: str


class EspRegistryPageResponse(BaseModel):
    """``GET /embedded-system-packages`` — cursor page of registry rows."""

    data: list[EspRegistryEntry]
    meta: CursorPageMeta


class EspResolverContract(BaseModel):
    """The resolver contract pinned to the current revision (``_contract_dict``).

    ``signature`` and ``evidence`` are caller-authored JSONB blobs rendered verbatim by the
    UI; they are OPEN objects here and must stay that way."""

    contract_id: str
    canonical_key: str
    signature: dict[str, Any]
    runtime_adapter: str
    warm_up_period: int | None
    timing_semantics: str | None
    repaint: bool
    evidence: dict[str, Any] | None


class EspValidationRunSummary(BaseModel):
    """Latest immutable validation-run evidence (``_validation_run_dict``, R8).

    ``checks`` is the STORED report envelope read straight out of JSONB — the whole
    ``ResolverValidationReport.as_dict()``, i.e. a dict, NOT the per-check list that the
    validate COMMAND returns under the same name. Rows written by an older
    ``validator_version`` may carry a different shape, so it stays an open object."""

    run_id: str
    status: str
    validator_version: str
    vectors_run: int
    checks: dict[str, Any]
    completed_at: str | None


class EspPackageDetailResponse(BaseModel):
    """``GET /embedded-system-packages/{entity_id}`` (``queries/esp.py::get_esp_detail``).

    ``lifecycle_state`` is nullable because ``entity_registry.lifecycle_state`` is a
    nullable free-form column, not a lifecycle enum — declaring it non-null would turn a
    null row into a 500 on an otherwise valid read.

    The three nested objects are INDEPENDENTLY nullable: ``contract`` is null when the
    revision has no resolver contract, ``registry`` is null when there is no contract or no
    registry row for its key, ``latest_validation_run`` is null until a run exists."""

    entity_id: str
    revision_id: str
    revision_no: int
    package_kind: str
    visibility_scope: str
    validation_state: str
    approval_state: str
    content_hash: str
    row_version: int
    lifecycle_state: str | None
    owner_principal_id: str | None
    contract: EspResolverContract | None
    registry: EspRegistryEntry | None
    latest_validation_run: EspValidationRunSummary | None
    created_at: str | None
    net_profit: str
    backtest_ready: str
    oos_passed: str


class CreateEspResponse(BaseModel):
    """``POST /embedded-system-packages`` (201). ``trust_state`` is always ``candidate``:
    a freshly created resolver is never trusted, activation is a separate Admin step."""

    entity_id: str
    revision_id: str
    canonical_key: str
    trust_state: str
    runtime_adapter: str


class EspValidationCheck(BaseModel):
    """One check line from ``domain/esp/validation.py::ResolverCheck.as_dict``."""

    name: str
    status: str
    detail: str


class EspValidationRunResponse(BaseModel):
    """``POST /embedded-system-packages/{entity_id}/validate``.

    ``checks`` here is the per-check LIST built in-process by the command — a closed,
    fixed-order shape — unlike the same-named stored envelope on the detail read. The two
    are deliberately different types and are not merged."""

    entity_id: str
    revision_id: str
    canonical_key: str
    validation_state: str
    vectors_run: int
    checks: list[EspValidationCheck]


class ActivateResolverResponse(BaseModel):
    """``POST /embedded-system-packages/{entity_id}/activate``. ``registry_version`` is the
    POST-increment value — the next ``X-Registry-Version`` OCC token the caller must send."""

    entity_id: str
    revision_id: str
    canonical_key: str
    trust_state: str
    registry_version: int


class DeprecateResolverResponse(BaseModel):
    """``POST /embedded-system-packages/{entity_id}/deprecate``.

    Deliberately NOT merged with ``ActivateResolverResponse``: deprecate reports the
    ``replacement_revision_id`` the caller nominated and carries no ``revision_id``, because
    deprecation targets the canonical key rather than one revision. Sharing one model would
    have made both fields optional and hidden which endpoint really returns which."""

    canonical_key: str
    entity_id: str
    trust_state: str
    replacement_revision_id: str | None
    registry_version: int


class ResolveDependencyResponse(BaseModel):
    """``POST /embedded-system-packages/resolve`` — Agent-Gateway/Pre-Check parity.

    ``resolved`` is always ``true`` on a 2xx: every non-resolution RAISES a typed error
    (404 not-resolved / 409 not-active / 409 adapter-incompatible / 422 signature-mismatch),
    so there is no ``{"resolved": false}`` body to model. The field is kept because the
    published contract and the frontend interface have always carried it."""

    resolved: bool
    canonical_key: str
    entity_id: str
    revision_id: str
    content_hash: str
    runtime_adapter: str
    registry_version: int
    signature: dict[str, Any]
    evidence: dict[str, Any] | None


__all__ = [
    "ActivateResolverResponse",
    "CreateEspResponse",
    "DeprecateResolverResponse",
    "EspPackageDetailResponse",
    "EspRegistryEntry",
    "EspRegistryPageResponse",
    "EspResolverContract",
    "EspValidationCheck",
    "EspValidationRunResponse",
    "EspValidationRunSummary",
    "ResolveDependencyResponse",
]
