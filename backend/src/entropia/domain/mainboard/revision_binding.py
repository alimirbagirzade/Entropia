"""Revision<->kind binding guard (doc 03 §11 "Revision/attachment", AOS-12 §14).

A Mainboard working item pins an exact ``root_id`` + ``revision_id`` (L5: never by
name, never by "latest"). Those two ids are supplied by the caller *independently*,
so a request can name a Trading Signal root and hand over a Trade Log revision id.
AOS-12 requires that this be answered by its own name — ``KIND_REVISION_MISMATCH``
— and that no partial working item is created.

Third guard in the item-kind family, and deliberately NOT a replacement for either
of the other two (see ``KindRevisionMismatchError`` for the full split):

* ``domain/package/kind.py``           — keeps the two external kinds out of ``PackageKind``.
* ``domain/mainboard/item_kind.py``    — client kind is unknown / a legacy alias.
* this module                          — the *revision's* kind disagrees with the kind being bound.

Fail-closed: the comparison is made against the revision row's own immutable
``object_kind`` column, never against anything the caller asserted, and it runs
BEFORE the generic "revision does not belong to this work object" check so the
cross-kind case is named by its own defect instead of disappearing into
``VALIDATION_ERROR``. Same-kind wrong-root stays generic on purpose: the spec names
no code for it, and inventing one here would outrun the contract.
"""

from __future__ import annotations

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.shared.errors import KindRevisionMismatchError


def assert_revision_kind_matches(
    *,
    revision_id: str,
    revision_kind: MainboardItemKind,
    expected_kind: MainboardItemKind,
    field: str = "revision_id",
) -> None:
    """Raise ``KindRevisionMismatchError`` (422) iff the revision's kind diverges.

    ``expected_kind`` is the SERVER-derived kind of the work object being bound
    (``work_object_detail.object_kind`` / the item's root), never a client-supplied
    ``item_kind`` — a client kind that disagrees with its own root is a different
    defect with a different code (CR-01 ``MAINBOARD_ITEM_KIND_MISMATCH``).
    """
    if revision_kind == expected_kind:
        return
    raise KindRevisionMismatchError(
        f"Revision {revision_id!r} is a {revision_kind.value} revision and cannot be "
        f"bound to a {expected_kind.value} work object.",
        details=[
            {
                "field": field,
                "actual": revision_id,
                "actual_kind": revision_kind.value,
                "expected_kind": expected_kind.value,
            }
        ],
        scope_id=revision_id,
        field_path=field,
    )
