"""Pure resolver-resolution predicates (doc 09 §4.2, §4.3, DC3)."""

from __future__ import annotations

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.esp.resolver import (
    ResolutionReason,
    evaluate_resolution,
    signature_matches,
)
from entropia.domain.lifecycle.enums import ApprovalState
from entropia.domain.package.enums import PackageValidationState

_SMA = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}


def _evaluate(**overrides):
    base = {
        "key_matches": True,
        "parsed_call_signature": _SMA,
        "contract_signature": _SMA,
        "contract_adapter": RuntimeAdapter.PINE_V5,
        "target_runtime": RuntimeAdapter.PINE_V5,
        "trust_state": ResolverTrustState.TRUSTED_ACTIVE,
        "validation_state": PackageValidationState.PASSED,
        "approval_state": ApprovalState.APPROVED,
    }
    base.update(overrides)
    return evaluate_resolution(**base)


def test_exact_signature_matches() -> None:
    assert signature_matches(_SMA, _SMA) is True


def test_reversed_arguments_are_not_a_match() -> None:
    reversed_call = {
        "params": [{"name": "length", "type": "int"}, {"name": "source", "type": "series"}],
        "return": "series",
    }
    assert signature_matches(reversed_call, _SMA) is False


def test_arity_mismatch_is_not_a_match() -> None:
    one_arg = {"params": [{"name": "source", "type": "series"}], "return": "series"}
    assert signature_matches(one_arg, _SMA) is False


def test_return_shape_mismatch_is_not_a_match() -> None:
    different_return = {**_SMA, "return": "bool"}
    assert signature_matches(different_return, _SMA) is False


def test_full_resolution_succeeds_when_all_gates_pass() -> None:
    assert _evaluate().reason == ResolutionReason.RESOLVED


def test_key_mismatch_reports_key_not_found() -> None:
    assert _evaluate(key_matches=False).reason == ResolutionReason.KEY_NOT_FOUND


def test_name_only_match_with_bad_signature_reports_mismatch() -> None:
    bad = {"params": [{"name": "x", "type": "int"}], "return": "series"}
    assert _evaluate(parsed_call_signature=bad).reason == ResolutionReason.SIGNATURE_MISMATCH


def test_incompatible_adapter_reports_adapter_incompatible() -> None:
    outcome = _evaluate(target_runtime=RuntimeAdapter.PYTHON)
    assert outcome.reason == ResolutionReason.ADAPTER_INCOMPATIBLE


def test_non_trusted_active_is_not_resolved() -> None:
    outcome = _evaluate(trust_state=ResolverTrustState.CANDIDATE)
    assert outcome.reason == ResolutionReason.NOT_TRUSTED_ACTIVE


def test_validation_not_passed_is_not_resolved() -> None:
    outcome = _evaluate(validation_state=PackageValidationState.WARNING)
    assert outcome.reason == ResolutionReason.VALIDATION_NOT_PASSED


def test_not_approved_is_not_resolved() -> None:
    outcome = _evaluate(approval_state=ApprovalState.APPROVAL_REQUESTED)
    assert outcome.reason == ResolutionReason.NOT_APPROVED
