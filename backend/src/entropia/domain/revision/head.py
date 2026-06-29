"""Root/revision head model helpers (DOMAIN_MODEL §1).

Each save INSERTs revision N+1 and advances the root's head pointer. Revisions
are immutable; they are never UPDATEd.
"""

from __future__ import annotations


def next_revision_no(current_revision_no: int | None) -> int:
    """First revision is 1; subsequent saves increment by one."""
    return 1 if current_revision_no is None else current_revision_no + 1
