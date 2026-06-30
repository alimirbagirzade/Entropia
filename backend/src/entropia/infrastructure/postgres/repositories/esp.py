"""ESP resolver registry persistence (doc 09 §4.1, DC2/DC4).

Sync mutators add resolver contract rows and upsert the canonical_key -> trusted
pointer (no commit, mirroring ``repositories/entities.py``); async readers return
ORM rows for the queries/resolution layer. Trust transitions and the
registry-version bump are applied by ``set_trust_state``; the application command
layer validates legality (state machine) and authorization (policy) first.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.infrastructure.postgres.models import (
    EmbeddedResolverContract,
    EmbeddedResolverRegistry,
)
from entropia.shared.ids import new_id


def add_resolver_contract(
    session: AsyncSession,
    *,
    entity_id: str,
    revision_id: str,
    canonical_key: str,
    signature: dict[str, Any],
    runtime_adapter: RuntimeAdapter,
    warm_up_period: int | None = None,
    timing_semantics: str | None = None,
    repaint: bool = False,
    evidence: dict[str, Any] | None = None,
) -> EmbeddedResolverContract:
    """Insert the immutable resolver contract for one ESP package revision."""
    contract = EmbeddedResolverContract(
        contract_id=new_id("espc"),
        entity_id=entity_id,
        revision_id=revision_id,
        canonical_key=canonical_key,
        signature=signature,
        runtime_adapter=runtime_adapter,
        warm_up_period=warm_up_period,
        timing_semantics=timing_semantics,
        repaint=repaint,
        evidence=evidence,
    )
    session.add(contract)
    return contract


def upsert_registry_entry(
    session: AsyncSession,
    *,
    canonical_key: str,
    package_entity_id: str,
    runtime_adapter: RuntimeAdapter,
    trust_state: ResolverTrustState = ResolverTrustState.CANDIDATE,
    trusted_active_revision_id: str | None = None,
    updated_by_principal_id: str | None = None,
) -> EmbeddedResolverRegistry:
    """Insert a new registry pointer row for a canonical_key (one active per key).

    This is an INSERT helper; mutation of an existing row's trust/pointer goes
    through ``set_trust_state`` so the registry version is bumped consistently.
    """
    entry = EmbeddedResolverRegistry(
        registry_id=new_id("espr"),
        canonical_key=canonical_key,
        package_entity_id=package_entity_id,
        trusted_active_revision_id=trusted_active_revision_id,
        trust_state=trust_state,
        runtime_adapter=runtime_adapter,
        registry_version=1,
        updated_by_principal_id=updated_by_principal_id,
    )
    session.add(entry)
    return entry


def set_trust_state(
    entry: EmbeddedResolverRegistry,
    *,
    trust_state: ResolverTrustState,
    trusted_active_revision_id: str | None = None,
    replacement_revision_id: str | None = None,
    updated_by_principal_id: str | None = None,
) -> EmbeddedResolverRegistry:
    """Apply a validated trust transition and bump the registry version.

    The caller must validate the transition (``domain/esp/state_machine.py``) and
    authorization (``domain/esp/policy.py``) before calling. ``registry_version``
    is incremented so a stale activation/deprecation is detected on the next
    optimistic-concurrency check (RESOLVER_REGISTRY_CONFLICT).
    """
    entry.trust_state = trust_state
    if trust_state == ResolverTrustState.TRUSTED_ACTIVE:
        entry.trusted_active_revision_id = trusted_active_revision_id
    elif trust_state in (ResolverTrustState.DEPRECATED, ResolverTrustState.UNAVAILABLE):
        entry.trusted_active_revision_id = None
    if replacement_revision_id is not None:
        entry.replacement_revision_id = replacement_revision_id
    entry.registry_version += 1
    if updated_by_principal_id is not None:
        entry.updated_by_principal_id = updated_by_principal_id
    return entry


async def get_registry_by_key(
    session: AsyncSession, canonical_key: str
) -> EmbeddedResolverRegistry | None:
    stmt = select(EmbeddedResolverRegistry).where(
        EmbeddedResolverRegistry.canonical_key == canonical_key
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_contract_by_revision(
    session: AsyncSession, revision_id: str
) -> EmbeddedResolverContract | None:
    stmt = select(EmbeddedResolverContract).where(
        EmbeddedResolverContract.revision_id == revision_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_resolvers(
    session: AsyncSession,
    *,
    trust_state: ResolverTrustState | None = None,
    limit: int = 50,
) -> Sequence[EmbeddedResolverRegistry]:
    """Registry pointer rows, optionally filtered by trust state."""
    stmt = (
        select(EmbeddedResolverRegistry)
        .order_by(EmbeddedResolverRegistry.canonical_key.asc())
        .limit(limit)
    )
    if trust_state is not None:
        stmt = stmt.where(EmbeddedResolverRegistry.trust_state == trust_state)
    return list((await session.execute(stmt)).scalars().all())


__all__ = [
    "add_resolver_contract",
    "get_contract_by_revision",
    "get_registry_by_key",
    "list_resolvers",
    "set_trust_state",
    "upsert_registry_entry",
]
