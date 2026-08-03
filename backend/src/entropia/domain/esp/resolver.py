"""Pure resolver-resolution predicates (doc 09 §4.3, §4.2).

No I/O. The application query layer fetches registry/contract rows and feeds
their plain dict ``signature`` payloads here. A resolver is *resolved* only when
ALL of these hold (doc 09 §4.2 Canonical Rule, §4.3 algorithm):

  1. the registry entry's Package Root exists and is an ``embedded_system``
     package (a registry pointer aimed at anything else is not a resolver),
  2. canonical resolver key matches,
  3. the parsed call signature is an exact compatible match (arity, ordered
     parameter types, return shape) — name-only is insufficient,
  4. the designated runtime adapter is compatible with the target runtime,
  5. the Package Root is LIFECYCLE-AVAILABLE: ``deletion_state=active`` and
     ``lifecycle_state=active`` — a soft-deleted / purge-pending / purged /
     deprecated root is never selectable for NEW work,
  6. trust state is ``trusted_active``,
  7. the active revision's validation state is ``passed`` and approval state is
     ``approved``.

Rule 5 is the lifecycle half that doc 09 §11.2 keeps SEPARATE from the registry
trust projection: the two facets are independent columns, so "the pointer still
says trusted_active" is not evidence that the root is still alive. Reading only
one of them is what let a soft-deleted resolver be pinned into a NEW Pre-Check.
Historical reads are unaffected — a pinned manifest names its exact revision id
and never comes through this function.

Each failing precondition has a distinct diagnostic reason code so the caller
can raise the exact typed error (doc 09 §9.2/§9.3, §11.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.lifecycle.enums import ApprovalState, DeletionState, PackageKind
from entropia.domain.package.enums import PackageValidationState

# The only ``lifecycle_state`` string a package root may carry and still be
# selectable for new work — mirrors ``commands/package_lifecycle.py::_ACTIVE``
# (the sibling value is ``"deprecated"``, written by ``deprecate_package``).
_ACTIVE_LIFECYCLE = "active"


class ResolutionReason(StrEnum):
    """Structured diagnostic for a resolution attempt (doc 09 §4.3 step 7)."""

    RESOLVED = "resolved"
    KEY_NOT_FOUND = "key_not_found"
    SIGNATURE_MISMATCH = "signature_mismatch"
    ADAPTER_INCOMPATIBLE = "adapter_incompatible"
    # The registry pointer names an entity that has no package root / detail row
    # at all: a dangling pointer is "no resolver", not "an inactive resolver".
    ROOT_MISSING = "root_missing"
    # The root exists but is not an ``embedded_system`` package — the registry is
    # pointing at some other package kind, so there is no resolver behind the key.
    WRONG_PACKAGE_KIND = "wrong_package_kind"
    # The root is soft-deleted / purge-pending / purged, or its domain lifecycle
    # was deprecated. Same doc 07 §12 RESOLVER_NOT_ACTIVE class as a deprecated
    # registry entry: the resolver exists, it is just not selectable any more.
    ROOT_NOT_ACTIVE = "root_not_active"
    # The registry entry exists but was deprecated-for-new-use or soft-deleted /
    # withdrawn — doc 07 §12 RESOLVER_NOT_ACTIVE. Kept separate from
    # NOT_TRUSTED_ACTIVE (a ``candidate`` that was never trusted in the first
    # place) because the remediation differs: activate vs. propose.
    RESOLVER_NOT_ACTIVE = "resolver_not_active"
    NOT_TRUSTED_ACTIVE = "not_trusted_active"
    VALIDATION_NOT_PASSED = "validation_not_passed"
    NOT_APPROVED = "not_approved"


# Trust states that mean "this resolver was trusted once and is not selectable for
# NEW conversions any more" — the doc 07 §12 RESOLVER_NOT_ACTIVE class. A
# ``candidate`` is NOT here: it was never trusted, so it stays NOT_TRUSTED_ACTIVE.
_INACTIVE_TRUST_STATES = frozenset({ResolverTrustState.DEPRECATED, ResolverTrustState.UNAVAILABLE})


@dataclass(frozen=True, slots=True)
class ResolverRootFacts:
    """The Package Root facets resolution needs, lifted out of the ORM row.

    Kept as a value object rather than three loose parameters so a caller cannot
    pass the lifecycle half and forget the deletion half — the exact omission
    this slice fixes. ``None`` in place of the whole object means the root (or
    its package detail row) does not exist -> ``ROOT_MISSING``.
    """

    deletion_state: DeletionState
    lifecycle_state: str | None
    package_kind: PackageKind

    @property
    def is_available_for_new_work(self) -> bool:
        """True only for a live, non-deprecated root (doc 09 §9.5, §11.2)."""
        return (
            self.deletion_state == DeletionState.ACTIVE
            and self.lifecycle_state == _ACTIVE_LIFECYCLE
        )


@dataclass(frozen=True, slots=True)
class ResolutionOutcome:
    """The pure result of evaluating a single candidate against a parsed call."""

    reason: ResolutionReason

    @property
    def is_resolved(self) -> bool:
        return self.reason == ResolutionReason.RESOLVED


def _params(signature: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the ordered parameter list from a signature payload.

    Accepts ``{"params": [{"name", "type"}, ...]}``; each entry is normalized to
    its ordered ``type`` for comparison. Missing/unknown types compare equal only
    when both sides agree, so an absent declared type never silently matches.
    """
    raw = signature.get("params")
    return list(raw) if isinstance(raw, list) else []


def signature_matches(
    parsed_call_signature: dict[str, Any], contract_signature: dict[str, Any]
) -> bool:
    """Exact-compatibility check between a parsed call and a contract signature.

    Compatible iff: same arity (number of ordered params), same ordered parameter
    types, and same return shape. Parameter *names* are not identity (doc 09
    §4.2 "display name is not identity"); ordered *types* are. A reversed-argument
    call (``ta.sma(length, source)`` vs ``ta.sma(source, length)``) fails here.
    """
    call_params = _params(parsed_call_signature)
    contract_params = _params(contract_signature)
    if len(call_params) != len(contract_params):
        return False
    for call_param, contract_param in zip(call_params, contract_params, strict=True):
        if call_param.get("type") != contract_param.get("type"):
            return False
    return parsed_call_signature.get("return") == contract_signature.get("return")


def _adapter_compatible(
    contract_adapter: RuntimeAdapter | str, target_runtime: RuntimeAdapter | str
) -> bool:
    """The designated adapter must match the requested target runtime exactly."""
    contract_value = (
        contract_adapter.value
        if isinstance(contract_adapter, RuntimeAdapter)
        else str(contract_adapter)
    )
    target_value = (
        target_runtime.value if isinstance(target_runtime, RuntimeAdapter) else str(target_runtime)
    )
    return contract_value == target_value


def evaluate_resolution(
    *,
    key_matches: bool,
    parsed_call_signature: dict[str, Any],
    contract_signature: dict[str, Any],
    contract_adapter: RuntimeAdapter | str,
    target_runtime: RuntimeAdapter | str,
    root_facts: ResolverRootFacts | None,
    trust_state: ResolverTrustState,
    validation_state: PackageValidationState,
    approval_state: ApprovalState,
) -> ResolutionOutcome:
    """Apply the full DC3 resolvability rules and return a structured outcome.

    The checks are ordered so the most specific diagnostic wins. STRUCTURAL
    identity comes first (is there a resolver behind this pointer at all — a
    dangling or wrong-kind root is not "an inactive resolver", it is no
    resolver), then the contract match (key, signature, adapter), then the
    AVAILABILITY plane: root lifecycle, registry trust, validation, approval.

    Root lifecycle is checked BEFORE trust on purpose. When both are wrong the
    root is the cause and the trust pointer is the stale symptom, so leading with
    the root gives the caller the actionable diagnostic.
    """
    if root_facts is None:
        return ResolutionOutcome(ResolutionReason.ROOT_MISSING)
    if root_facts.package_kind != PackageKind.EMBEDDED_SYSTEM:
        return ResolutionOutcome(ResolutionReason.WRONG_PACKAGE_KIND)
    if not key_matches:
        return ResolutionOutcome(ResolutionReason.KEY_NOT_FOUND)
    if not signature_matches(parsed_call_signature, contract_signature):
        return ResolutionOutcome(ResolutionReason.SIGNATURE_MISMATCH)
    if not _adapter_compatible(contract_adapter, target_runtime):
        return ResolutionOutcome(ResolutionReason.ADAPTER_INCOMPATIBLE)
    if not root_facts.is_available_for_new_work:
        return ResolutionOutcome(ResolutionReason.ROOT_NOT_ACTIVE)
    if trust_state in _INACTIVE_TRUST_STATES:
        return ResolutionOutcome(ResolutionReason.RESOLVER_NOT_ACTIVE)
    if trust_state != ResolverTrustState.TRUSTED_ACTIVE:
        return ResolutionOutcome(ResolutionReason.NOT_TRUSTED_ACTIVE)
    if validation_state != PackageValidationState.PASSED:
        return ResolutionOutcome(ResolutionReason.VALIDATION_NOT_PASSED)
    if approval_state != ApprovalState.APPROVED:
        return ResolutionOutcome(ResolutionReason.NOT_APPROVED)
    return ResolutionOutcome(ResolutionReason.RESOLVED)
