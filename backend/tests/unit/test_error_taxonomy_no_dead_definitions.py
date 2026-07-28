"""O-03: nothing in the error taxonomy may be a name the code can never produce.

A declared-but-never-raised error class is worse than a missing one: it reads as a
supported contract in ``errors.py``, gets quoted in specs and reviews, and silently
promises a response shape that no request can ever receive. This module pins the
exact set of such classes so the number can only go down without a deliberate edit.

The O-03 sweep removed two dead definitions (``PrecheckAlreadyRunning`` and
``DeletePolicyBlocked``). Five never-raised error classes remain as recorded debt in
``KNOWN_UNRAISED``; adding a sixth fails here.

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

# Declared but never raised anywhere in src/. Recorded debt, NOT an allowance to grow:
# each entry is a class whose feature was specified but never built.
KNOWN_UNRAISED = frozenset(
    {
        "RoleContextStaleError",
        "ValidationAlreadyRunning",
        "ServiceUnavailableError",
        "ArtifactNotAvailableError",
        "HypothesisArtifactNotFoundError",
    }
)

# Removed by O-03 — these names must not come back without a code path that raises them.
REMOVED_BY_O03 = ("PrecheckAlreadyRunning", "DeletePolicyBlocked")
REMOVED_CODES_BY_O03 = ("PRECHECK_ALREADY_RUNNING", "DELETE_POLICY_BLOCKED")


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
