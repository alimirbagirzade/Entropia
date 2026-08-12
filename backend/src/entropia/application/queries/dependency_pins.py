"""Approve-time re-validation of a revision's pinned ESP resolver refs (doc 06 §7).

Doc 06 §7 names *"dependencies active"* among the Approve Package preconditions,
next to the validation-eligible and mode-aware baseline gates. Pre-Check resolves
and pins the refs (doc 07 §8), but Pre-Check and Approve are two separate human
steps: a resolver that was ``trusted_active`` when the scan ran can be deprecated,
withdrawn or un-approved before an Admin presses Approve. Without a re-check the
draft would publish against a resolver the registry no longer trusts — the exact
window this module closes.

What is re-checked, and what is deliberately NOT:

* The registry entry for each pinned canonical key must still exist and still be
  ``trusted_active`` (``domain/esp/enums.py::ResolverTrustState``). ``deprecated``
  and ``unavailable`` are reported apart from ``candidate`` because the remediation
  differs (activate a replacement vs. propose one), mirroring the Pre-Check
  diagnostics in ``domain/esp/resolver.py::ResolutionReason``.
* The pinned ESP revision must still be ``passed`` + ``approved`` — the same
  step-5 rule Pre-Check applied, re-read from the row that can have moved since.
* Signature/adapter compatibility is NOT re-checked: a revision's contract is
  immutable, so what Pre-Check matched cannot have drifted.
* A pin that is no longer the registry's ``trusted_active_revision_id`` while the
  KEY is still trusted is NOT rejected. Doc 09 §11.2 keeps historical pins
  readable; superseding a revision is not the same event as withdrawing trust.

Fail-closed: any pin this module cannot positively confirm as active raises
``DEPENDENCY_UNRESOLVED`` (doc 06 §7 error list) before the approval mutates a row,
so the draft survives for repair.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.esp.enums import ResolverTrustState
from entropia.domain.lifecycle.enums import ApprovalState
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import EmbeddedResolverRegistry, PackageRevision
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import DependencyUnresolved

# Per-pin defect vocabulary carried in the error envelope's ``details``. The trust
# reasons keep the Pre-Check spelling (``domain/esp/resolver.py``) so a user sees
# one vocabulary across the two surfaces.
PIN_UNREADABLE = "pinned_ref_unreadable"
RESOLVER_KEY_NOT_FOUND = "key_not_found"
RESOLVER_NOT_ACTIVE = "resolver_not_active"
RESOLVER_NOT_TRUSTED_ACTIVE = "not_trusted_active"
PINNED_REVISION_MISSING = "pinned_revision_missing"
PINNED_REVISION_NOT_PASSED = "validation_not_passed"
PINNED_REVISION_NOT_APPROVED = "not_approved"

# "Trusted once, not selectable for new work any more" — kept apart from
# ``candidate`` (never trusted), mirroring ``domain/esp/resolver.py``.
_INACTIVE_TRUST_STATES = frozenset({ResolverTrustState.DEPRECATED, ResolverTrustState.UNAVAILABLE})


def pinned_resolver_refs(dependency_snapshot: Any) -> list[dict[str, Any]]:
    """The pinned resolver refs of a dependency snapshot, or ``[]``.

    Tolerates every shape a snapshot can legally take (a description-route request
    pins ``{"resolved": [], "source": "description"}``); a malformed payload yields
    no refs here and is caught by the gates that own that contract.
    """
    if not isinstance(dependency_snapshot, dict):
        return []
    resolved = dependency_snapshot.get("resolved")
    if not isinstance(resolved, list):
        return []
    return [ref for ref in resolved if isinstance(ref, dict)]


def _ref_key(ref: dict[str, Any]) -> str:
    """The canonical key a ref names, or ``""`` when it names none."""
    return str(ref.get("canonical_key") or ref.get("call") or "")


def _pinned_revision_id(ref: dict[str, Any], entry: EmbeddedResolverRegistry) -> str:
    """The revision whose evidence this ref stands on, or ``""``.

    The exact revision the draft pinned is what must still carry the evidence. A ref
    that named no revision falls back to the key's current trusted revision — the
    revision such a claim would resolve to — instead of being waved through. This is
    why the revision batch can only be built AFTER the registry batch.
    """
    return str(ref.get("embedded_revision_id") or entry.trusted_active_revision_id or "")


def _pin_defect(
    ref: dict[str, Any],
    entries: dict[str, EmbeddedResolverRegistry],
    revisions: dict[str, PackageRevision],
) -> str | None:
    """The reason this pinned ref is not active, or ``None`` when it still is.

    Pure over the two prefetched maps (#618). A key or revision id absent from its map
    is the same ``None`` the per-ref readers returned, so every defect term is still
    produced for the same input — a pin the batch cannot positively confirm stays a
    defect, never a pass.
    """
    key = _ref_key(ref)
    if not key:
        return PIN_UNREADABLE
    entry = entries.get(key)
    if entry is None:
        return RESOLVER_KEY_NOT_FOUND
    if entry.trust_state in _INACTIVE_TRUST_STATES:
        return RESOLVER_NOT_ACTIVE
    if entry.trust_state != ResolverTrustState.TRUSTED_ACTIVE:
        return RESOLVER_NOT_TRUSTED_ACTIVE
    revision_id = _pinned_revision_id(ref, entry)
    revision = revisions.get(revision_id) if revision_id else None
    if revision is None:
        return PINNED_REVISION_MISSING
    if revision.validation_state != PackageValidationState.PASSED:
        return PINNED_REVISION_NOT_PASSED
    if revision.approval_state != ApprovalState.APPROVED:
        return PINNED_REVISION_NOT_APPROVED
    return None


async def _prefetch(
    session: AsyncSession, refs: list[dict[str, Any]]
) -> tuple[dict[str, EmbeddedResolverRegistry], dict[str, PackageRevision]]:
    """Both sides of the per-pin check, in two queries regardless of pin count (#618).

    The order is not an implementation detail: a ref with no ``embedded_revision_id``
    resolves to its registry entry's ``trusted_active_revision_id``, so the revision
    ids are only knowable once the registry map exists. A ref whose key is missing
    contributes no revision id — it is already ``key_not_found``, and letting it fall
    back would drag an unrelated row into the batch.
    """
    entries = await esp_repo.get_registry_by_keys(
        session, [key for ref in refs if (key := _ref_key(ref))]
    )
    revision_ids: list[str] = []
    for ref in refs:
        entry = entries.get(_ref_key(ref))
        if entry is None:
            continue
        if revision_id := _pinned_revision_id(ref, entry):
            revision_ids.append(revision_id)
    return entries, await pkg_repo.get_revisions(session, revision_ids)


async def ensure_pinned_resolvers_active(
    session: AsyncSession,
    *,
    dependency_snapshot: Any,
    scope_id: str,
) -> None:
    """Reject an approval whose pinned resolvers are no longer active (doc 06 §7).

    Raises ``DependencyUnresolved`` listing EVERY offending pin — one round trip
    tells the owner all the refs to repair, not just the first. Nothing is mutated,
    so the draft is still there when the registry is fixed or Pre-Check is re-run.
    """
    refs = pinned_resolver_refs(dependency_snapshot)
    entries, revisions = await _prefetch(session, refs)
    issues: list[dict[str, Any]] = []
    for ref in refs:
        defect = _pin_defect(ref, entries, revisions)
        if defect is None:
            continue
        issues.append(
            {
                "canonical_key": ref.get("canonical_key") or ref.get("call"),
                "embedded_revision_id": ref.get("embedded_revision_id"),
                "issue": defect,
            }
        )
    if not issues:
        return
    raise DependencyUnresolved(
        "A pinned dependency is no longer active. Re-run Pre-Check and try again.",
        details=issues,
        scope_type="PackageRevision",
        scope_id=scope_id,
        field_path="dependency_snapshot.resolved",
        suggested_action="rerun_precheck",
        remediation=(
            "The registry no longer trusts one of the pinned resolvers. Activate a "
            "replacement resolver or re-run Pre-Check so the draft pins a trusted "
            "revision, then request approval again."
        ),
    )


__all__ = [
    "ensure_pinned_resolvers_active",
    "pinned_resolver_refs",
]
