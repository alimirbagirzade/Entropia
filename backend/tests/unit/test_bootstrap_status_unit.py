"""Unit: first-Admin bootstrap `configured` flag (pure, no infra).

The `active_admin_exists` half of `bootstrap_status` needs a DB session, so it
is exercised in tests/integration/test_bootstrap_status.py. Here we pin only the
pure operator-opt-in predicate that gates the status query and the sign-up
bootstrap branch.
"""

from __future__ import annotations

from entropia.application.commands.auth import bootstrap_is_configured


def test_set_email_is_configured() -> None:
    assert bootstrap_is_configured("founder@example.com")


def test_leading_trailing_whitespace_still_configured() -> None:
    assert bootstrap_is_configured("  founder@example.com  ")


def test_unset_is_not_configured() -> None:
    assert not bootstrap_is_configured(None)
    assert not bootstrap_is_configured("")


def test_whitespace_only_is_not_configured() -> None:
    # A blank/whitespace env value is the same as unset — the mechanism is off.
    assert not bootstrap_is_configured("   ")
