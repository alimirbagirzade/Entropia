"""Unit: first-Admin bootstrap email matching (pure, no infra)."""

from __future__ import annotations

from entropia.application.commands.auth import bootstrap_admin_matches


def test_exact_match() -> None:
    assert bootstrap_admin_matches("ops@example.com", "ops@example.com")


def test_case_insensitive_match() -> None:
    assert bootstrap_admin_matches("Ops@Example.COM", "ops@example.com")
    assert bootstrap_admin_matches("ops@example.com", "OPS@EXAMPLE.COM")


def test_whitespace_normalized() -> None:
    assert bootstrap_admin_matches("  ops@example.com ", "ops@example.com")
    assert bootstrap_admin_matches("ops@example.com", " ops@example.com  ")


def test_non_matching_email() -> None:
    assert not bootstrap_admin_matches("other@example.com", "ops@example.com")


def test_unset_bootstrap_disables_mechanism() -> None:
    assert not bootstrap_admin_matches("ops@example.com", None)
    assert not bootstrap_admin_matches("ops@example.com", "")


def test_missing_signup_email_never_matches() -> None:
    assert not bootstrap_admin_matches(None, "ops@example.com")
    assert not bootstrap_admin_matches("", "ops@example.com")
    assert not bootstrap_admin_matches(None, None)
