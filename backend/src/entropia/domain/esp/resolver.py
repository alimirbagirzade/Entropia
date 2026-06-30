"""Pure resolver-resolution predicates (doc 09 §4.3, §4.2).

No I/O. The application query layer fetches registry/contract rows and feeds
their plain dict ``signature`` payloads here. A resolver is *resolved* only when
ALL of these hold (doc 09 §4.2 Canonical Rule, §4.3 algorithm):

  1. canonical resolver key matches,
  2. the parsed call signature is an exact compatible match (arity, ordered
     parameter types, return shape) — name-only is insufficient,
  3. the designated runtime adapter is compatible with the target runtime,
  4. trust state is ``trusted_active``,
  5. the active revision's validation state is ``passed`` and approval state is
     ``approved``.

Each failing precondition has a distinct diagnostic reason code so the caller
can raise the exact typed error (doc 09 §9.2/§9.3, §11.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.lifecycle.enums import ApprovalState
from entropia.domain.package.enums import PackageValidationState


class ResolutionReason(StrEnum):
    """Structured diagnostic for a resolution attempt (doc 09 §4.3 step 7)."""

    RESOLVED = "resolved"
    KEY_NOT_FOUND = "key_not_found"
    SIGNATURE_MISMATCH = "signature_mismatch"
    ADAPTER_INCOMPATIBLE = "adapter_incompatible"
    NOT_TRUSTED_ACTIVE = "not_trusted_active"
    VALIDATION_NOT_PASSED = "validation_not_passed"
    NOT_APPROVED = "not_approved"


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
    trust_state: ResolverTrustState,
    validation_state: PackageValidationState,
    approval_state: ApprovalState,
) -> ResolutionOutcome:
    """Apply the full DC3 resolvability rules and return a structured outcome.

    The checks are ordered so the most specific diagnostic wins: key, then
    signature, then adapter, then trust/validation/approval gates.
    """
    if not key_matches:
        return ResolutionOutcome(ResolutionReason.KEY_NOT_FOUND)
    if not signature_matches(parsed_call_signature, contract_signature):
        return ResolutionOutcome(ResolutionReason.SIGNATURE_MISMATCH)
    if not _adapter_compatible(contract_adapter, target_runtime):
        return ResolutionOutcome(ResolutionReason.ADAPTER_INCOMPATIBLE)
    if trust_state != ResolverTrustState.TRUSTED_ACTIVE:
        return ResolutionOutcome(ResolutionReason.NOT_TRUSTED_ACTIVE)
    if validation_state != PackageValidationState.PASSED:
        return ResolutionOutcome(ResolutionReason.VALIDATION_NOT_PASSED)
    if approval_state != ApprovalState.APPROVED:
        return ResolutionOutcome(ResolutionReason.NOT_APPROVED)
    return ResolutionOutcome(ResolutionReason.RESOLVED)
