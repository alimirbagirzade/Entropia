"""Restore preflight conflict taxonomy + typed resolution catalog (doc 20 §5
"Restore conflict choice", §6 "Restore needs attention", §8.2).

O-17: ``RestoreConflictError`` used to be raised BARE. The Admin got a 409 with
no alternatives, so doc 20 §8.2's rule — the Admin may pick ONLY from the typed
resolutions the domain adapter offers — had nothing to select from, and the §6
panel had no ``{conflict_summary}`` to render. It lives here so BOTH the read-only
preflight (``queries/trash.py::get_restore_preflight``) and the command raise
sites (``commands/deletion.py``) answer from ONE table.

Two rules the generic Trash handler must not break (doc 20 §5, §8.2):

* **No invented fix.** A conflict kind offers exactly the resolutions its domain
  adapter supports. ``TARGET_MISSING`` deliberately offers NONE — there is no
  honest repair for a record that left the state machine, so the command cannot
  be started and the root stays ``soft_deleted``.
* **No silent repair.** An unknown or unsupported ``resolution`` is a typed 422
  (``UnsupportedRestoreResolutionError``) — never ignored, never coerced.

Adding a conflict kind means adding its row to ``_CONFLICT_SUMMARY`` **and**
``_RESOLUTIONS``; a kind with no entry would render an empty panel.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from entropia.shared.errors import RestoreConflictError, UnsupportedRestoreResolutionError


class RestoreConflictKind(StrEnum):
    """Why restore preflight refused (doc 20 §8.2). Wire value — never renamed."""

    # The deletion snapshot pinned a head revision; the record moved since.
    HEAD_POINTER_MOVED = "head_pointer_moved"
    # The target row is no longer resolvable — it left the state machine.
    TARGET_MISSING = "target_missing"


class RestoreResolution(StrEnum):
    """A resolution a domain adapter actually supports (doc 20 §5). Wire value."""

    # Reactivate at the head the record points to NOW, instead of the head the
    # deletion snapshot recorded. This is a HUMAN decision — the restore path
    # never adopts a moved head on its own (doc 20 §10 historical integrity).
    RESTORE_AT_CURRENT_HEAD = "restore_at_current_head"


_CONFLICT_SUMMARY: dict[RestoreConflictKind, str] = {
    RestoreConflictKind.HEAD_POINTER_MOVED: (
        "the object's revision pointer moved after it was deleted"
    ),
    RestoreConflictKind.TARGET_MISSING: ("the object's underlying record is no longer resolvable"),
}

# The ONLY source of "what may this Admin choose". An empty tuple is a real
# answer: no supported alternative exists (doc 20 §8.2).
_RESOLUTIONS: dict[RestoreConflictKind, tuple[RestoreResolution, ...]] = {
    RestoreConflictKind.HEAD_POINTER_MOVED: (RestoreResolution.RESTORE_AT_CURRENT_HEAD,),
    RestoreConflictKind.TARGET_MISSING: (),
}

_RESOLUTION_COPY: dict[RestoreResolution, tuple[str, str]] = {
    RestoreResolution.RESTORE_AT_CURRENT_HEAD: (
        "Restore at the current revision pointer",
        "Reactivate the object at the revision it points to now instead of the "
        "revision recorded in the deletion snapshot. No revision is created, "
        "rewritten or rolled back, and the deletion snapshot stays unchanged as "
        "evidence of what was deleted.",
    ),
}

_NO_RESOLUTION_REMEDIATION = (
    "No supported resolution is available for this conflict. The object remains "
    "in Trash; investigate the underlying record before retrying."
)
_HAS_RESOLUTION_REMEDIATION = (
    "Choose one of the listed domain-specific resolutions and retry the restore "
    "with the same expected deletion version."
)


def conflict_summary(
    kind: RestoreConflictKind,
    *,
    expected_head: Any = None,
    current_head: Any = None,
) -> str:
    """The ``{conflict_summary}`` doc 20 §6 interpolates into the panel body."""
    summary = _CONFLICT_SUMMARY[kind]
    if kind is RestoreConflictKind.HEAD_POINTER_MOVED:
        return (
            f"{summary} (the deletion snapshot recorded '{expected_head}', "
            f"the record now points to '{current_head}')"
        )
    return summary


def resolution_options(kind: RestoreConflictKind) -> list[dict[str, str]]:
    """The typed option set for a conflict — human-readable, machine-selectable."""
    options: list[dict[str, str]] = []
    for resolution in _RESOLUTIONS[kind]:
        label, description = _RESOLUTION_COPY[resolution]
        options.append(
            {
                "conflict_kind": str(kind),
                "resolution": str(resolution),
                "label": label,
                "description": description,
            }
        )
    return options


def supports_resolution(kind: RestoreConflictKind, resolution: RestoreResolution | None) -> bool:
    """Is ``resolution`` one this conflict's domain adapter actually offers?"""
    return resolution is not None and resolution in _RESOLUTIONS[kind]


def parse_resolution(raw: str | None) -> RestoreResolution | None:
    """Body token -> typed resolution. Unknown/unsupported -> 422 (doc 20 §5).

    Deliberately NOT a pydantic enum on the request model: a pydantic coercion
    failure would emit the framework's generic 422 body instead of the canonical
    error envelope, and "no resolution supplied" (``None``) must stay distinct
    from "a resolution the catalog does not know".
    """
    if raw is None:
        return None
    try:
        return RestoreResolution(raw)
    except ValueError:
        raise UnsupportedRestoreResolutionError(
            details=[
                {
                    "field": "resolution",
                    "issue": f"'{raw}' is not a supported restore resolution.",
                    "supported": [str(value) for value in RestoreResolution],
                }
            ],
            scope_id=raw,
        ) from None


def restore_conflict(
    kind: RestoreConflictKind,
    *,
    entity_type: str,
    entity_id: str,
    expected_head: Any = None,
    current_head: Any = None,
) -> RestoreConflictError:
    """Build the 409 the restore path raises — WITH its alternatives (O-17).

    ``message`` carries the ``{conflict_summary}``, ``details`` carries one row
    per supported typed resolution (empty when none exists), and ``remediation``
    spells out the next human step. Nothing here applies a repair.
    """
    options = resolution_options(kind)
    return RestoreConflictError(
        conflict_summary(kind, expected_head=expected_head, current_head=current_head),
        details=options,
        remediation=_HAS_RESOLUTION_REMEDIATION if options else _NO_RESOLUTION_REMEDIATION,
        scope_type=entity_type,
        scope_id=entity_id,
    )


__all__ = [
    "RestoreConflictKind",
    "RestoreResolution",
    "conflict_summary",
    "parse_resolution",
    "resolution_options",
    "restore_conflict",
    "supports_resolution",
]
