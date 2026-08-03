"""Pure resolver-resolution predicates (doc 09 §4.2, §4.3, DC3)."""

from __future__ import annotations

import pytest

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.esp.resolver import (
    ResolutionReason,
    ResolverRootFacts,
    evaluate_resolution,
    signature_matches,
)
from entropia.domain.lifecycle.enums import ApprovalState, DeletionState, PackageKind
from entropia.domain.package.enums import PackageValidationState

_SMA = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}

_LIVE_ROOT = ResolverRootFacts(
    deletion_state=DeletionState.ACTIVE,
    lifecycle_state="active",
    package_kind=PackageKind.EMBEDDED_SYSTEM,
)


def _evaluate(**overrides):
    base = {
        "key_matches": True,
        "parsed_call_signature": _SMA,
        "contract_signature": _SMA,
        "contract_adapter": RuntimeAdapter.PINE_V5,
        "target_runtime": RuntimeAdapter.PINE_V5,
        "root_facts": _LIVE_ROOT,
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


def test_deprecated_resolver_reports_not_active() -> None:
    """doc 07 §12 RESOLVER_NOT_ACTIVE: the key exists but was deprecated for new use.
    Distinct from a candidate that was never trusted — the remediation differs."""
    outcome = _evaluate(trust_state=ResolverTrustState.DEPRECATED)
    assert outcome.reason == ResolutionReason.RESOLVER_NOT_ACTIVE
    assert outcome.is_resolved is False


def test_soft_deleted_resolver_reports_not_active() -> None:
    outcome = _evaluate(trust_state=ResolverTrustState.UNAVAILABLE)
    assert outcome.reason == ResolutionReason.RESOLVER_NOT_ACTIVE


def test_validation_not_passed_is_not_resolved() -> None:
    outcome = _evaluate(validation_state=PackageValidationState.WARNING)
    assert outcome.reason == ResolutionReason.VALIDATION_NOT_PASSED


def test_not_approved_is_not_resolved() -> None:
    outcome = _evaluate(approval_state=ApprovalState.APPROVAL_REQUESTED)
    assert outcome.reason == ResolutionReason.NOT_APPROVED


# --------------------------------------------------------------------------- #
# Root lifecycle gate (doc 09 §9.5, §11.2; doc 07 §12 / PC-19)                  #
# --------------------------------------------------------------------------- #


def test_missing_root_reports_root_missing() -> None:
    """A dangling registry pointer is "no resolver", not "an inactive resolver" —
    so it maps to RESOLVER_NOT_RESOLVED (propose one), not RESOLVER_NOT_ACTIVE."""
    outcome = _evaluate(root_facts=None)
    assert outcome.reason == ResolutionReason.ROOT_MISSING
    assert outcome.is_resolved is False


def test_non_embedded_package_kind_is_not_a_resolver() -> None:
    outcome = _evaluate(
        root_facts=ResolverRootFacts(
            deletion_state=DeletionState.ACTIVE,
            lifecycle_state="active",
            package_kind=PackageKind.INDICATOR,
        )
    )
    assert outcome.reason == ResolutionReason.WRONG_PACKAGE_KIND


@pytest.mark.parametrize(
    "deletion_state",
    [DeletionState.SOFT_DELETED, DeletionState.PURGE_PENDING, DeletionState.PURGED],
)
def test_non_active_deletion_state_closes_the_resolver(deletion_state) -> None:
    """PC-19 second clause: a root that has left ACTIVE is never selectable for NEW
    work, whatever the registry pointer still claims. Every non-active deletion
    state answers alike — purge_pending is not a grace period."""
    outcome = _evaluate(
        root_facts=ResolverRootFacts(
            deletion_state=deletion_state,
            lifecycle_state="active",
            package_kind=PackageKind.EMBEDDED_SYSTEM,
        )
    )
    assert outcome.reason == ResolutionReason.ROOT_NOT_ACTIVE


@pytest.mark.parametrize("lifecycle_state", ["deprecated", None, ""])
def test_non_active_lifecycle_state_closes_the_resolver(lifecycle_state) -> None:
    """``deprecate_package`` writes ``"deprecated"``; NULL/empty is a root that never
    declared a lifecycle. Neither is ``"active"``, so neither is selectable — the
    gate is an allow-list, not a deny-list."""
    outcome = _evaluate(
        root_facts=ResolverRootFacts(
            deletion_state=DeletionState.ACTIVE,
            lifecycle_state=lifecycle_state,
            package_kind=PackageKind.EMBEDDED_SYSTEM,
        )
    )
    assert outcome.reason == ResolutionReason.ROOT_NOT_ACTIVE


def test_root_lifecycle_outranks_a_stale_trust_pointer() -> None:
    """When the root is dead AND the pointer still says trusted_active, the root is
    the cause and the pointer is the stale symptom — lead with the actionable one."""
    outcome = _evaluate(
        root_facts=ResolverRootFacts(
            deletion_state=DeletionState.SOFT_DELETED,
            lifecycle_state="active",
            package_kind=PackageKind.EMBEDDED_SYSTEM,
        ),
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
    )
    assert outcome.reason == ResolutionReason.ROOT_NOT_ACTIVE


def test_contract_mismatch_still_outranks_the_root_gate() -> None:
    """Signature/adapter are contract identity and stay the more specific diagnostic:
    a caller with a reversed-argument call learns that, not "root not active"."""
    bad = {"params": [{"name": "x", "type": "int"}], "return": "series"}
    outcome = _evaluate(
        parsed_call_signature=bad,
        root_facts=ResolverRootFacts(
            deletion_state=DeletionState.SOFT_DELETED,
            lifecycle_state="active",
            package_kind=PackageKind.EMBEDDED_SYSTEM,
        ),
    )
    assert outcome.reason == ResolutionReason.SIGNATURE_MISMATCH
