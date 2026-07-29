"""O-03: nothing in the error taxonomy may be a name the code can never produce.

A declared-but-never-raised error class is worse than a missing one: it reads as a
supported contract in ``errors.py``, gets quoted in specs and reviews, and silently
promises a response shape that no request can ever receive. This module pins the
exact set of such classes so the number can only go down without a deliberate edit.

The O-03 sweep removed two dead definitions (``PrecheckAlreadyRunning`` and
``DeletePolicyBlocked``) and pinned five more as recorded debt. That debt is now
ZERO: ``ValidationAlreadyRunning`` earned a raise path in S-L3, and O-03R adjudicated
the remaining four (see ``REMOVED_BY_O03R``). ``KNOWN_UNRAISED`` is therefore empty
and the ratchet is absolute — ANY never-raised error class fails this module now.
Do not re-open the set: the only ways forward are a real raise path or no class.

A third candidate, ``PublicationState.REMOVED``, was dead when this sweep began and
is deliberately NOT removed: O-15 (PR #409) landed the purge-time redaction that
assigns it while O-03 was in review. That is the standing lesson here — this file
recomputes the dead set from the tree on every run rather than trusting a list
written when someone last looked.
"""

import re
from pathlib import Path

_ERRORS_FILE = Path(__file__).resolve().parents[2] / "src" / "entropia" / "shared" / "errors.py"
_SRC_ROOT = _ERRORS_FILE.parents[2]

# Declared but never raised anywhere in src/. EMPTY, and it stays empty: a class with
# no raise path is either given one or deleted. ``ValidationAlreadyRunning`` left this
# set in S-L3 by earning a raise path (the Library-plane Request Validation command
# raises it when the CP request is already in ``validation_running``); the last four
# left it in O-03R by being deleted. The "resurrected" assertion below is what forced
# the S-L3 entry out rather than letting it sit here as a stale allowance.
KNOWN_UNRAISED: frozenset[str] = frozenset()

# Removed by O-03 — these names must not come back without a code path that raises them.
REMOVED_BY_O03 = ("PrecheckAlreadyRunning", "DeletePolicyBlocked")
REMOVED_CODES_BY_O03 = ("PRECHECK_ALREADY_RUNNING", "DELETE_POLICY_BLOCKED")

# Removed by O-03R. Each was spec-visible but structurally unreachable; re-adding one
# without a raiser must be a deliberate act, so each carries its adjudication here:
#
# * ``RoleContextStaleError`` / ``ROLE_CONTEXT_STALE`` — Master Technical Reference
#   §11.1 (domain error-code table) fires it when "the caller session's role revision is
#   stale". No session carries a role revision: ``auth_sessions`` stores only
#   (session_id, user_id, token_hash, issued_at, expires_at, revoked_at), and
#   ``apps/api/deps.py`` re-resolves the role from the registry on EVERY request
#   (M1 §4.2). The spec's own remedy column — "session context is refreshed, the
#   request is re-evaluated with the new role" — is what the code does
#   unconditionally, so no request can ever be left holding a stale role to reject.
# * ``ServiceUnavailableError`` / ``SERVICE_UNAVAILABLE`` — zero occurrences of the
#   code (or of "503") anywhere in ``docs/spec/``. Named dependency outages have
#   their own spec-anchored classes (e.g. ``ValidationPipelineUnavailable``, doc 08
#   §7). A generic 503 advertising ``retryable=True`` that nothing can emit is the
#   exact false promise this module exists to prevent.
# * ``ArtifactNotAvailableError`` / ``ARTIFACT_NOT_AVAILABLE`` — doc 15 §7 names it
#   for ``QueryResultArtifact`` alongside ``RETENTION_EXPIRED`` and integrity
#   failure, and §5 gates the view on "retention availability". That whole family is
#   unbuilt: no retention/availability/checksum column on the result row, and
#   neither sibling code is even declared. Retention purge is a recorded V1
#   exclusion (doc 20 §16). An empty page is NOT this error — a run with no trades
#   has a legitimately empty ledger, so 404-ing it would invent a failure.
# * ``HypothesisArtifactNotFoundError`` / ``HYPOTHESIS_NOT_FOUND`` — zero occurrences
#   of the code in ``docs/spec/``; doc 18 exposes hypotheses only as a board/list
#   (§3 HYPOTHESIS & OUTPUT BOARD, §8.1 overview summaries, §9 artifact model,
#   §14 "board is filled by hypothesis_artifact queries"), with no
#   single-artifact detail endpoint to serve a 404 — unlike agent tasks and tool
#   calls, whose NotFound siblings ARE raised. The three by-id lookups that exist
#   answer in another taxonomy on purpose: ``ARTIFACT_NOT_OWNED`` (AL-16, doc 18
#   §12) and the Trash conflict codes (doc 20 §11).
REMOVED_BY_O03R = (
    "RoleContextStaleError",
    "ServiceUnavailableError",
    "ArtifactNotAvailableError",
    "HypothesisArtifactNotFoundError",
)
REMOVED_CODES_BY_O03R = (
    "ROLE_CONTEXT_STALE",
    "SERVICE_UNAVAILABLE",
    "ARTIFACT_NOT_AVAILABLE",
    "HYPOTHESIS_NOT_FOUND",
)


def _declared_error_classes() -> list[str]:
    return re.findall(r"^class\s+(\w+)\(", _ERRORS_FILE.read_text(), re.M)


def _source_outside_errors_module() -> str:
    return "\n".join(path.read_text() for path in _SRC_ROOT.rglob("*.py") if path != _ERRORS_FILE)


def test_no_new_never_raised_error_classes() -> None:
    """Every error class is referenced by real code, except the recorded debt set."""
    blob = _source_outside_errors_module()
    unraised = {name for name in _declared_error_classes() if name not in blob}

    new_dead = unraised - KNOWN_UNRAISED
    assert not new_dead, (
        f"New never-raised error class(es): {sorted(new_dead)}. Either raise them from a "
        "real code path or do not declare them."
    )

    resurrected = KNOWN_UNRAISED - unraised
    assert not resurrected, (
        f"{sorted(resurrected)} are now raised — remove them from KNOWN_UNRAISED so the "
        "ratchet keeps tightening."
    )


def test_o03_removed_classes_stay_removed() -> None:
    declared = _declared_error_classes()
    for name in REMOVED_BY_O03:
        assert name not in declared, f"{name} was removed by O-03 as never-raised."

    text = _ERRORS_FILE.read_text()
    for code in REMOVED_CODES_BY_O03:
        assert code not in text, f"Error code {code} was removed by O-03 as never-emitted."


def test_o03r_removed_classes_stay_removed() -> None:
    """The four O-03R deletions do not creep back as declarations-without-raisers.

    ``test_no_new_never_raised_error_classes`` already fails on a re-added class with
    no raise path; this one is the narrower statement the adjudication earned — these
    four specific names were proven unreachable, so bringing one back is a decision
    that has to survive reading the block above, not an accident.
    """
    declared = _declared_error_classes()
    for name in REMOVED_BY_O03R:
        assert name not in declared, f"{name} was removed by O-03R as never-raised."

    text = _ERRORS_FILE.read_text()
    for code in REMOVED_CODES_BY_O03R:
        assert code not in text, f"Error code {code} was removed by O-03R as never-emitted."


def test_recorded_debt_is_empty() -> None:
    """O-03R drove the never-raised debt to zero; re-opening it is a deliberate edit.

    Without this, someone could quietly re-add an entry to ``KNOWN_UNRAISED`` and the
    module above would go green again — the ratchet would silently loosen.
    """
    assert not KNOWN_UNRAISED, (
        "KNOWN_UNRAISED must stay empty: a never-raised error class is either given a "
        f"real raise path or deleted. Re-opened with: {sorted(KNOWN_UNRAISED)}."
    )
