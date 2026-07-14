"""Resolve each composition item's traded-instrument settlement currency (doc 13 §5.1).

Impure, read-only helper used by the allocation validate / plan-revision commands and
the Ready Check path to feed ``AllocationItemRef.settlement_currency`` into the pure
``validate_allocation`` FX cross-check. A composition item pins an exact work object
revision; that revision resolves to a canonical ``instrument_id`` whose registry row
carries the ``settlement_asset`` (the settlement currency):

* STRATEGY: pinned work object revision payload -> (doc 02 §7.1 mirror deref) ->
  ``data.instrument_id`` -> instrument registry ``settlement_asset``.
* TRADING_SIGNAL: the pinned normalized signal-event revision's ``instrument_id``.
* TRADE_LOG: the pinned canonical trade-record batch's ``instrument_id``.

Any unresolved link (no pin, no ``instrument_id``, the instrument absent, or a null
``settlement_asset``) yields ``None`` — the pure check then SKIPS that item, so a
currency difference is never fabricated from missing metadata (doc 13 §5.1).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.infrastructure.postgres.models import MainboardWorkingItem
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo


async def resolve_settlement_currencies(
    session: AsyncSession, items: Sequence[MainboardWorkingItem]
) -> dict[str, str | None]:
    """Map ``item_id -> settlement currency`` (``None`` when unresolvable)."""
    result: dict[str, str | None] = {}
    for item in items:
        result[item.item_id] = await _resolve_one(session, item)
    return result


async def _resolve_one(session: AsyncSession, item: MainboardWorkingItem) -> str | None:
    instrument_id = await _instrument_id_for(session, item)
    if not instrument_id:
        return None
    instrument = await instrument_repo.get_instrument(session, instrument_id)
    return instrument.settlement_asset if instrument is not None else None


async def _instrument_id_for(session: AsyncSession, item: MainboardWorkingItem) -> str | None:
    if item.item_kind == MainboardItemKind.STRATEGY:
        return await _strategy_instrument_id(session, item.pinned_revision_id)
    if item.item_kind == MainboardItemKind.TRADING_SIGNAL:
        revision = await readiness_repo.resolve_signal_revision(session, item.pinned_revision_id)
        return revision.instrument_id if revision is not None else None
    if item.item_kind == MainboardItemKind.TRADE_LOG:
        batch = await readiness_repo.resolve_trade_log_batch(session, item.pinned_revision_id)
        return batch.instrument_id if batch is not None else None
    return None


async def _strategy_instrument_id(session: AsyncSession, pinned_revision_id: str) -> str | None:
    """Dereference a strategy pin (direct config or the §7.1 mirror) to ``data.instrument_id``."""
    revision = await mb_repo.get_work_object_revision(session, pinned_revision_id)
    if revision is None:
        return None
    payload: dict[str, Any] = dict(revision.payload)
    mirror_ref = payload.get("strategy_revision_id")
    if mirror_ref:
        strat_rev = await strat_repo.get_strategy_revision(session, str(mirror_ref))
        if strat_rev is not None:
            payload = dict(strat_rev.payload)
    data = payload.get("data")
    raw = data.get("instrument_id") if isinstance(data, dict) else None
    text = str(raw).strip() if raw is not None else ""
    return text or None


__all__ = ["resolve_settlement_currencies"]
