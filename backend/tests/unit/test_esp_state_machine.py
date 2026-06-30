"""ESP resolver trust state machine (doc 09 §11.2)."""

from __future__ import annotations

import pytest

from entropia.domain.esp.enums import ResolverTrustState
from entropia.domain.esp.state_machine import (
    IllegalResolverTrustTransition,
    can_activate,
    can_deprecate,
    next_resolver_trust_state,
)


def test_activate_only_from_candidate() -> None:
    assert can_activate(ResolverTrustState.CANDIDATE) is True
    assert can_activate(ResolverTrustState.TRUSTED_ACTIVE) is False
    assert can_activate(ResolverTrustState.DEPRECATED) is False


def test_deprecate_only_from_trusted_active() -> None:
    assert can_deprecate(ResolverTrustState.TRUSTED_ACTIVE) is True
    assert can_deprecate(ResolverTrustState.CANDIDATE) is False
    assert can_deprecate(ResolverTrustState.DEPRECATED) is False


def test_candidate_can_activate() -> None:
    assert (
        next_resolver_trust_state(ResolverTrustState.CANDIDATE, ResolverTrustState.TRUSTED_ACTIVE)
        == ResolverTrustState.TRUSTED_ACTIVE
    )


def test_trusted_active_can_deprecate() -> None:
    assert (
        next_resolver_trust_state(ResolverTrustState.TRUSTED_ACTIVE, ResolverTrustState.DEPRECATED)
        == ResolverTrustState.DEPRECATED
    )


def test_cannot_activate_a_deprecated_resolver() -> None:
    with pytest.raises(IllegalResolverTrustTransition):
        next_resolver_trust_state(ResolverTrustState.DEPRECATED, ResolverTrustState.TRUSTED_ACTIVE)


def test_cannot_skip_candidate_to_deprecated() -> None:
    with pytest.raises(IllegalResolverTrustTransition):
        next_resolver_trust_state(ResolverTrustState.CANDIDATE, ResolverTrustState.DEPRECATED)


def test_unavailable_is_terminal() -> None:
    with pytest.raises(IllegalResolverTrustTransition):
        next_resolver_trust_state(ResolverTrustState.UNAVAILABLE, ResolverTrustState.TRUSTED_ACTIVE)
