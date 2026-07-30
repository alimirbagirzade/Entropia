"""The three Run Manifest field groups a pin alone cannot carry (K-04, doc 15 §9.2).

doc 15 §9.2 mandates SEVEN manifest field groups. Identity, Mainboard items,
Capital/execution and Result-artifact context are derivable from the composition
snapshot, so the Stage 5a builder already carried them. The remaining three —
Strategy/package, External object and Data/time context — only exist BEHIND a
dereference, so before K-04 the worker resolved them itself at RUN time
(``resolve_indicator_plan``, the market/research revision reads) and the immutable
manifest carried no proof of WHICH revisions a Result was produced from.

This module resolves those three groups ONCE at admission, walking exactly the
dereference paths the worker already walks — no new business logic, only recording:

* Strategy / package — the Strategy-editor mirror pin -> the real ``StrategyConfig``
  -> every enabled entry/exit/logic-stop block's pinned indicator package, its nested
  condition packages and their reference chain (the same traversal
  ``resolve_indicator_plan`` performs), each with its Strategy-local parameter
  overrides, plus each package revision's frozen ``dependency_snapshot['resolved']``
  resolver refs (the transitive Embedded System Package revision ids).
* External object — the Trading Signal / Trade Log work-object revision's import
  binding + mapping/timezone/availability/price-source policy, and the normalized
  event revision / canonical trade-record batch it pins (the Ready Check deref).
* Data / time — the pinned market dataset revision (resolution, timezone, record time
  basis) + its coverage digest + the strategy's backtest range and execution timing,
  and every research feed the engine consumes (V1: the funding source) with its
  available-time policy, join/instrument mapping and field-definition version.

Everything is RECORDED, nothing is judged here: a pin that no longer resolves is still
written (its id with a null detail) so the worker's ``_unresolved_pins`` gate fails the
run closed (``RUN_FAILED_MANIFEST_RESOLUTION``) instead of falling back to the current
Mainboard or a 'latest' revision (doc 15 §15).

Honest boundary: only the research feed the V1 engine actually consumes (funding) is
pinned as a research dataset — the manifest never claims a feed the engine does not read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.readiness_check import _resolve_strategy_payload
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.strategy.config import FundingPolicy, StrategyConfig
from entropia.domain.strategy.pins import SCALING_ROLE, iter_pinned_packages
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo

_FUNDING_ROLE = "funding"


@dataclass(frozen=True, slots=True)
class RunManifestContext:
    """The three resolved manifest field groups (doc 15 §9.2)."""

    strategy_package: list[dict[str, Any]]
    external_objects: list[dict[str, Any]]
    data_time: list[dict[str, Any]]


async def resolve_run_manifest_context(
    session: AsyncSession, item_manifest: dict[str, Any] | None
) -> RunManifestContext:
    """Resolve the strategy/package, external-object and data/time groups.

    Items are consumed in the snapshot's own order and each group is sorted by
    ``item_id`` so the manifest (and therefore its hashes) is order-stable.

    O-24b: every enabled item's work-object revision is dereferenced in ONE batch up
    front instead of once per item. An id with no row is simply absent from the map, so
    the ``is None`` skip below is unchanged — a pin that no longer resolves still drops
    out of these three groups and is still caught by the worker's ``_unresolved_pins``
    gate from ``mainboard_items``."""
    strategy_package: list[dict[str, Any]] = []
    external_objects: list[dict[str, Any]] = []
    data_time: list[dict[str, Any]] = []
    raw = item_manifest.get("items", []) if isinstance(item_manifest, dict) else []
    revisions = await mb_repo.get_work_object_revisions(
        session,
        [
            str(entry["revision_id"])
            for entry in raw
            if entry.get("enabled") is not False and entry.get("revision_id") is not None
        ],
    )
    for entry in raw:
        if entry.get("enabled") is False:
            continue
        revision_id = entry.get("revision_id")
        if revision_id is None:
            continue
        revision = revisions.get(str(revision_id))
        if revision is None:
            continue
        item_id = str(entry.get("item_id"))
        kind = entry.get("kind")
        if kind != MainboardItemKind.STRATEGY:
            external_objects.append(await _external_entry(session, item_id, str(kind), revision))
            continue
        payload = dict(revision.payload or {})
        mirror_ref = payload.get("strategy_revision_id")
        resolved = await _resolve_strategy_payload(session, payload)
        try:
            config = StrategyConfig.model_validate(resolved)
        except ValidationError:
            # Readiness STRATEGY_CONFIG_INVALID gates this upstream; a config that does
            # not parse pins nothing beyond the work-object revision already in
            # ``mainboard_items``.
            continue
        strategy_package.append(
            await _strategy_entry(
                session,
                item_id=item_id,
                work_object_revision_id=str(revision.revision_id),
                strategy_revision_id=str(mirror_ref) if mirror_ref else None,
                config=config,
            )
        )
        data_time.append(await _data_time_entry(session, item_id=item_id, config=config))
    return RunManifestContext(
        strategy_package=sorted(strategy_package, key=lambda e: str(e["item_id"])),
        external_objects=sorted(external_objects, key=lambda e: str(e["item_id"])),
        data_time=sorted(data_time, key=lambda e: str(e["item_id"])),
    )


# --------------------------------------------------------------------------- #
# Strategy / package context                                                  #
# --------------------------------------------------------------------------- #


async def _strategy_entry(
    session: AsyncSession,
    *,
    item_id: str,
    work_object_revision_id: str,
    strategy_revision_id: str | None,
    config: StrategyConfig,
) -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    resolvers: dict[str, dict[str, Any]] = {}
    # The shared traversal returns every package the RESOLVER dereferences, which now
    # includes the S5c Logic-Based Scaling group. The manifest has never recorded that
    # group, and adding it here would change ``package_revisions`` — and therefore the
    # ``execution_key`` — for every scaling strategy. That is a reproducibility decision,
    # not a side effect of a batching change, so the scaling pins are dropped explicitly
    # (a visible boundary) rather than by narrowing the traversal, which would leave the
    # resolver's own pins unprefetched.
    pins = [p for p in iter_pinned_packages(config) if not p.role.startswith(SCALING_ROLE)]
    # O-24b: one IN() read for the whole pin set, not one per block/condition/leg. A pin
    # with no row is absent from the map, so ``revision is None`` below still records the
    # id with a null detail for the worker's fail-closed gate.
    revisions = await pkg_repo.get_revisions(session, [p.ref.package_revision_id for p in pins])
    for pinned in pins:
        revision = revisions.get(pinned.ref.package_revision_id)
        packages.append(
            {
                "role": pinned.role,
                "block_id": pinned.block_id,
                "condition_block_id": pinned.condition_block_id,
                "leg_index": pinned.leg_index,
                "package_root_id": pinned.ref.package_root_id,
                "package_revision_id": pinned.ref.package_revision_id,
                "pinned_content_hash": pinned.ref.package_content_hash,
                "parameter_overrides": pinned.parameter_overrides,
                "revision": (
                    None
                    if revision is None
                    else {
                        "package_kind": str(revision.package_kind),
                        "content_hash": revision.content_hash,
                        "validation_state": str(revision.validation_state),
                        "approval_state": str(revision.approval_state),
                    }
                ),
            }
        )
        if revision is not None:
            for ref in _resolver_refs(revision.dependency_snapshot):
                resolvers[str(ref["embedded_revision_id"])] = ref
    return {
        "item_id": item_id,
        "work_object_revision_id": work_object_revision_id,
        "strategy_revision_id": strategy_revision_id,
        "strategy_root_id": config.strategy_root_id,
        "rationale_family_id": config.rationale_family_id,
        "package_revisions": packages,
        "resolver_revisions": [resolvers[key] for key in sorted(resolvers)],
    }


def _resolver_refs(dependency_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The frozen resolver refs a package revision pinned (Pre-Check ``resolved``).

    Each ref is an EXACT Embedded System Package revision + content hash + registry
    version (doc 06/07 P4/L5 — never name-only/latest), so the manifest carries the
    transitive dependency identity, not just the top-level package id."""
    resolved = None
    if isinstance(dependency_snapshot, dict):
        resolved = dependency_snapshot.get("resolved")
    if not isinstance(resolved, list):
        return []
    refs: list[dict[str, Any]] = []
    for entry in resolved:
        if not isinstance(entry, dict):
            continue
        embedded_revision_id = entry.get("embedded_revision_id")
        if not embedded_revision_id:
            continue
        refs.append(
            {
                "canonical_key": entry.get("canonical_key"),
                "embedded_entity_id": entry.get("embedded_entity_id"),
                "embedded_revision_id": str(embedded_revision_id),
                "content_hash": entry.get("content_hash"),
                "runtime_adapter": entry.get("runtime_adapter"),
                "registry_version": entry.get("registry_version"),
            }
        )
    return refs


# --------------------------------------------------------------------------- #
# External object context                                                     #
# --------------------------------------------------------------------------- #


async def _external_entry(
    session: AsyncSession, item_id: str, kind: str, revision: Any
) -> dict[str, Any]:
    """The Trading Signal / Trade Log import pin + its policy snapshot (doc 15 §9.2).

    Policy sub-objects are read verbatim from the pinned work-object revision payload
    (the immutable config the page saved); the import revision itself is dereferenced
    through the SAME repository probe Ready Check uses."""
    payload = dict(revision.payload or {})
    entry: dict[str, Any] = {
        "item_id": item_id,
        "item_kind": kind,
        "work_object_revision_id": str(revision.revision_id),
        "import_binding": payload.get("import_binding"),
        "price_policy": payload.get("price_policy"),
        "ohlcv_policy": payload.get("ohlcv_policy"),
        "data_quality": payload.get("data_quality"),
    }
    if kind == MainboardItemKind.TRADE_LOG:
        batch = await readiness_repo.resolve_trade_log_batch(session, str(revision.revision_id))
        entry["time_model"] = payload.get("time_model")
        entry["canonical_record_batch"] = (
            None
            if batch is None
            else {
                "record_batch_revision_id": batch.record_batch_id,
                "source_asset_id": batch.source_asset_id,
                "status": str(batch.status),
                "instrument_id": batch.instrument_id,
                "accepted_count": batch.accepted_count,
                "skipped_count": batch.skipped_count,
                "content_hash": batch.content_hash,
                "earliest_entry_time": _iso(batch.earliest_entry_time),
                "latest_exit_time": _iso(batch.latest_exit_time),
                "validation_summary": batch.validation_summary,
            }
        )
        return entry
    normalized = await readiness_repo.resolve_signal_revision(session, str(revision.revision_id))
    entry["time_policy"] = payload.get("time_policy")
    entry["event_model"] = payload.get("event_model")
    entry["normalized_event_revision"] = (
        None
        if normalized is None
        else {
            "normalized_event_revision_id": normalized.normalized_revision_id,
            "source_asset_id": normalized.source_asset_id,
            "status": str(normalized.status),
            "instrument_id": normalized.instrument_id,
            "accepted_count": normalized.accepted_count,
            "skipped_count": normalized.skipped_count,
            "content_hash": normalized.content_hash,
            "earliest_available_time": _iso(normalized.earliest_available_time),
            "validation_summary": normalized.validation_summary,
        }
    )
    return entry


# --------------------------------------------------------------------------- #
# Data / time context                                                         #
# --------------------------------------------------------------------------- #


async def _data_time_entry(
    session: AsyncSession, *, item_id: str, config: StrategyConfig
) -> dict[str, Any]:
    data = config.data
    revision_id = data.market_dataset_revision_id
    revision = await md_repo.get_revision(session, revision_id)
    coverage = await md_repo.summarize_coverage_for_revisions(session, [revision_id])
    research = await _research_entries(session, data.funding)
    return {
        "item_id": item_id,
        "instrument_id": data.instrument_id,
        "market_dataset_root_id": data.market_dataset_root_id,
        "market_dataset_revision_id": revision_id,
        "pinned_content_hash": data.market_dataset_content_hash,
        "market_dataset": (
            None
            if revision is None
            else {
                "entity_id": revision.entity_id,
                "revision_state": str(revision.revision_state),
                "market_data_type": str(revision.market_data_type),
                "resolution_kind": _enum(revision.resolution_kind),
                "resolution_value": revision.resolution_value,
                "timezone_mode": _enum(revision.timezone_mode),
                "timezone_iana": revision.timezone_iana,
                "record_time_basis": _enum(revision.record_time_basis),
                "instrument_id": revision.instrument_id,
                "content_hash": revision.content_hash,
            }
        ),
        # Absent when the analysis job has not covered the revision yet — an honest
        # null, never a fabricated span (the registry projection's P-09 rule).
        "coverage": coverage.get(revision_id),
        "backtest_range": {"start": data.backtest_range.start, "end": data.backtest_range.end},
        "execution": {
            "entry_timing": str(data.execution.entry_timing),
            "exit_timing": str(data.execution.exit_timing),
        },
        "research_dataset_revision_ids": [
            str(feed["revision_id"]) for feed in research if feed["revision_id"]
        ],
        "research_datasets": research,
    }


async def _research_entries(session: AsyncSession, funding: FundingPolicy) -> list[dict[str, Any]]:
    """The research feeds the V1 engine consumes: the pinned funding source only.

    Mirrors ``resolve_funding_schedule``'s deref (doc 12 §8.4): the revision's
    available-time policy + delay, its market join and instrument mapping ref, the
    declared source timezone and the field/feature definition versions. Funding OFF
    pins nothing (the engine resolves no schedule)."""
    if not funding.enabled:
        return []
    revision_id = funding.source_revision_id
    revision = await research_repo.get_revision(session, revision_id) if revision_id else None
    features: list[dict[str, Any]] = []
    if revision is not None:
        features = [
            {
                "feature_definition_id": feature.feature_definition_id,
                "feature_name": feature.feature_name,
                "feature_version": feature.feature_version,
                "content_hash": feature.content_hash,
                "approval_state": feature.approval_state,
            }
            for feature in await research_repo.list_feature_definitions(
                session, revision.revision_id
            )
        ]
    return [
        {
            "role": _FUNDING_ROLE,
            "root_id": funding.source_root_id,
            "revision_id": revision_id,
            "pinned_content_hash": funding.source_content_hash,
            "revision": (
                None
                if revision is None
                else {
                    "entity_id": revision.entity_id,
                    "revision_state": str(revision.revision_state),
                    "category_key": revision.category_key,
                    "usage_scope": _enum(revision.usage_scope),
                    "content_hash": revision.content_hash,
                    "available_time_policy": _enum(revision.available_time_policy),
                    "available_delay_seconds": revision.available_delay_seconds,
                    "event_time_semantics": _enum(revision.event_time_semantics),
                    "frequency_policy": _enum(revision.frequency_policy),
                    "source_timezone_mode": _enum(revision.source_timezone_mode),
                    "source_timezone_iana": revision.source_timezone_iana,
                    "linked_market_dataset_revision_id": (
                        revision.linked_market_dataset_revision_id
                    ),
                    "instrument_mapping_ref": revision.instrument_mapping_ref,
                    "field_definition_version": revision.field_definition_version,
                    "feature_definitions": features,
                }
            ),
        }
    ]


def _enum(value: Any) -> str | None:
    return None if value is None else str(value)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


__all__ = ["RunManifestContext", "resolve_run_manifest_context"]
