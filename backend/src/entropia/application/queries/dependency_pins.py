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


async def _pin_defect(session: AsyncSession, ref: dict[str, Any]) -> str | None:
    """The reason this pinned ref is not active, or ``None`` when it still is."""
    key = str(ref.get("canonical_key") or ref.get("call") or "")
    if not key:
        return PIN_UNREADABLE
    entry = await esp_repo.get_registry_by_key(session, key)
    if entry is None:
        return RESOLVER_KEY_NOT_FOUND
    if entry.trust_state in _INACTIVE_TRUST_STATES:
        return RESOLVER_NOT_ACTIVE
    if entry.trust_state != ResolverTrustState.TRUSTED_ACTIVE:
        return RESOLVER_NOT_TRUSTED_ACTIVE
    # The exact revision the draft pinned is what must still carry the evidence. A
    # ref that named no revision falls back to the key's current trusted revision —
    # the revision such a claim would resolve to — instead of being waved through.
    revision_id = str(ref.get("embedded_revision_id") or entry.trusted_active_revision_id or "")
    revision = await pkg_repo.get_revision(session, revision_id) if revision_id else None
    if revision is None:
        return PINNED_REVISION_MISSING
    if revision.validation_state != PackageValidationState.PASSED:
        return PINNED_REVISION_NOT_PASSED
    if revision.approval_state != ApprovalState.APPROVED:
        return PINNED_REVISION_NOT_APPROVED
    return None


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
    issues: list[dict[str, Any]] = []
    for ref in pinned_resolver_refs(dependency_snapshot):
        defect = await _pin_defect(session, ref)
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
