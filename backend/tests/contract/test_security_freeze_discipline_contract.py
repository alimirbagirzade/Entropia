"""A security finding may only be waived in ONE place, and only with a signature.

Until ADIM 44 this repo had two freeze idioms with different rules. The container
scan read ``.github/security-allowlist.json``, which requires an ``owner`` and an
``expires`` and fails the build once the date passes. The npm audit gate carried
its own ``FROZEN_ADVISORIES`` literal, which required neither — so an npm freeze
was a waiver nobody was accountable for and no calendar could ever expire. The RC
readiness report recorded that asymmetry as blocker P9-B2 (§6.4).

The asymmetry was closed by deletion: the literal is gone and both gates read the
same signed allowlist. That is a property a future edit can silently undo — by
re-introducing a hardcoded list, by gating a directory whose scope was never
declared, or by adding an entry with a blank owner. Each of those failures looks
like a passing build. So they are pinned here.

What this file does NOT assert: that any particular finding is or is not waived.
``entries`` is empty today because nothing needs waiving; a future signed entry
must not turn this file red.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

ALLOWLIST = REPO_ROOT / ".github" / "security-allowlist.json"
SHARED_MODULE = REPO_ROOT / "scripts" / "lib" / "security-allowlist.mjs"
NPM_GATE = REPO_ROOT / "scripts" / "npm-audit-gate.mjs"
CONTAINER_GATE = REPO_ROOT / "scripts" / "security-allowlist-gate.mjs"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SECURITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security.yml"

#: The six fields ``loadAllowlist`` refuses to load an entry without. Duplicated
#: from the module on purpose: this test's job is to fail when the module's list
#: is quietly shortened, which it could not do by importing the same value.
REQUIRED_FIELDS = ("id", "scope", "package", "owner", "justification", "expires")

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def allowlist() -> dict:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))


def _gate_invocations(workflow: Path, script: str) -> list[str]:
    """Every ``run:`` line block in *workflow* that invokes *script*, flattened."""
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    out: list[str] = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            run = step.get("run")
            if run and script in run:
                # Line continuations make one logical command span several lines.
                out.append(" ".join(run.replace("\\\n", " ").split()))
    return out


# --------------------------------------------------------------------------- #
# The allowlist is well-formed and every entry carries a signature.
# --------------------------------------------------------------------------- #
def test_every_entry_carries_all_required_fields(allowlist: dict) -> None:
    for i, entry in enumerate(allowlist["entries"]):
        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            assert isinstance(value, str) and value.strip(), (
                f"entries[{i}] is missing '{field}'. An exception without an owner is a "
                f"waiver nobody is accountable for; without an expiry it is one no "
                f"calendar can ever revisit."
            )
        assert ISO_DATE.match(entry["expires"]), (
            f"entries[{i}].expires={entry['expires']!r} is not YYYY-MM-DD"
        )
        assert entry["scope"] in allowlist["scopes"], (
            f"entries[{i}].scope={entry['scope']!r} is not a declared scope"
        )


def test_owner_is_a_person_not_a_team_alias(allowlist: dict) -> None:
    # The file's own words: "the human accountable for revisiting it, not a team
    # alias". A generic mailbox cannot be paged and cannot be asked why.
    forbidden = ("team", "@", "-ops", "group", "everyone", "n/a", "tbd", "unknown")
    for i, entry in enumerate(allowlist["entries"]):
        owner = entry["owner"].lower()
        for token in forbidden:
            assert token not in owner, (
                f"entries[{i}].owner={entry['owner']!r} looks like an alias, not a named "
                f"human ({token!r})."
            )


# --------------------------------------------------------------------------- #
# There is exactly one place a freeze may be written.
# --------------------------------------------------------------------------- #
def test_npm_gate_declares_no_hardcoded_freeze_list() -> None:
    source = NPM_GATE.read_text(encoding="utf-8")
    # Prose may still name the deleted literal — that history is worth keeping.
    # A DECLARATION of it is what must never come back.
    assert not re.search(r"^\s*(const|let|var)\s+FROZEN_ADVISORIES", source, re.M), (
        "scripts/npm-audit-gate.mjs re-declares FROZEN_ADVISORIES. That is a second "
        "home for a freeze, and it requires neither an owner nor an expiry — exactly "
        "the asymmetry blocker P9-B2 recorded. Put the entry in "
        ".github/security-allowlist.json instead."
    )


def test_both_gates_read_the_shared_allowlist_module() -> None:
    assert SHARED_MODULE.exists(), f"{SHARED_MODULE} is missing"
    for gate in (NPM_GATE, CONTAINER_GATE):
        source = gate.read_text(encoding="utf-8")
        assert "lib/security-allowlist.mjs" in source, (
            f"{gate.name} no longer imports the shared allowlist reader, so its "
            f"validation and expiry rules can drift from the other gate's."
        )
        assert "enforceExpiry" in source, (
            f"{gate.name} does not call enforceExpiry. Every gate expires the WHOLE "
            f"list: otherwise an exception's calendar depends on which workflow ran."
        )


def test_max_exception_days_is_declared_once() -> None:
    # A cap written down twice is a cap that will disagree with itself.
    assert "MAX_EXCEPTION_DAYS = 90" in SHARED_MODULE.read_text(encoding="utf-8")
    for gate in (NPM_GATE, CONTAINER_GATE):
        assert "MAX_EXCEPTION_DAYS =" not in gate.read_text(encoding="utf-8"), (
            f"{gate.name} re-declares MAX_EXCEPTION_DAYS; the cap lives in "
            f"scripts/lib/security-allowlist.mjs alone."
        )


# --------------------------------------------------------------------------- #
# Every gated surface is a declared scope, and every declared scope is gated.
# --------------------------------------------------------------------------- #
def test_ci_npm_dirs_match_the_declared_npm_scopes(allowlist: dict) -> None:
    invocations = _gate_invocations(CI_WORKFLOW, "npm-audit-gate.mjs")
    assert invocations, "ci.yml no longer runs the npm audit gate at all"

    gated: set[str] = set()
    for command in invocations:
        args = command.split("npm-audit-gate.mjs", 1)[1].split()
        gated.update(f"npm:{arg}" for arg in args)

    declared = {s for s in allowlist["scopes"] if s.startswith("npm:")}
    assert gated == declared, (
        f"ci.yml gates {sorted(gated)} but the allowlist declares {sorted(declared)}. "
        f"An undeclared scope reads as 'nothing is waived here' when it actually means "
        f"'this surface was never declared'; a declared-but-ungated scope is a surface "
        f"nobody scans."
    )


def test_security_workflow_container_scopes_match_the_declared_ones(allowlist: dict) -> None:
    invocations = _gate_invocations(SECURITY_WORKFLOW, "security-allowlist-gate.mjs")
    assert invocations, "security.yml no longer runs the container allowlist gate"

    gated = {
        arg.split("=", 1)[0]
        for command in invocations
        for arg in command.split("security-allowlist-gate.mjs", 1)[1].split()
        if "=" in arg
    }
    declared = {s for s in allowlist["scopes"] if s.startswith("container:")}
    assert gated == declared, (
        f"security.yml scans {sorted(gated)} but the allowlist declares {sorted(declared)}."
    )
