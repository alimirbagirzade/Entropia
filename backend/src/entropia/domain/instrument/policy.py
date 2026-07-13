"""Instrument registry authorization policy (GAP-16; Master §8.1).

Any authenticated actor may register a canonical instrument (reference data the
whole workspace shares) and read the registry. Deprecating an instrument closes
new selection for everyone, so it is Admin-only — an Agent/Supervisor/User that
reaches the call receives ``InstrumentDeprecateRequiresAdminError`` (403).
"""

from __future__ import annotations

from entropia.domain.identity.actor import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.shared.errors import InstrumentDeprecateRequiresAdminError


def ensure_can_register(actor: Actor) -> None:
    """Registration is open to any authenticated actor (reference data)."""
    require_authenticated(actor)


def ensure_can_deprecate(actor: Actor) -> None:
    """Deprecating a canonical instrument is Admin-only (closes new selection)."""
    require_authenticated(actor)
    if not actor.is_admin:
        raise InstrumentDeprecateRequiresAdminError(
            "Deprecating a canonical instrument requires the Admin role."
        )
