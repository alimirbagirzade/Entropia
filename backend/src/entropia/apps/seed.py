"""Seed baseline identities for local development.

    python -m entropia.apps.seed

Creates (idempotently) a default Admin human user and the non-login system
Agent. Intended for local/staging bootstrap only — production identity
provisioning is part of the deferred security/IdP decision.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from entropia.config import get_settings
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.instrument.enums import ContractType
from entropia.domain.instrument.scope import normalize_alias, resolution_key
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.rationale import normalized_name, pick_color
from entropia.domain.research_data.enums import ResearchRevisionState, UsageScope
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.models import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_ADMIN_ID = os.getenv("SEED_ADMIN_ID", "user_admin")
DEFAULT_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
DEFAULT_AGENT_ID = os.getenv("SEED_AGENT_ID", "agent_alpha")
SEED_DEMO_MARKET = os.getenv("SEED_DEMO_MARKET", "0") == "1"
SEED_E2E_GOLDEN = os.getenv("SEED_E2E_GOLDEN", "0") == "1"
SEED_DEMO_RESEARCH = os.getenv("SEED_DEMO_RESEARCH", "0") == "1"
SEED_ESP_TA = os.getenv("SEED_ESP_TA", "0") == "1"
SEED_RATIONALE = os.getenv("SEED_RATIONALE", "0") == "1"
SEED_INSTRUMENTS = os.getenv("SEED_INSTRUMENTS", "0") == "1"

# Canonical instrument seeds (GAP-16; Master §8.1). Each: (venue, symbol,
# contract_type, display_name, base, quote, settlement, market_class, aliases).
# The identity triple keeps spot vs perpetual distinct; the aliases resolve the
# free-text UI scope ("BTCUSDT Perpetual") to the exact canonical instrument.
_INSTRUMENT_SEEDS: tuple[
    tuple[str, str, str, ContractType, str, str, str, str, tuple[str, ...]], ...
] = (
    (
        "binance",
        "BTCUSDT",
        "BTCUSDT Perpetual",
        ContractType.PERPETUAL,
        "BTC",
        "USDT",
        "USDT",
        "crypto",
        ("BTCUSDT Perpetual", "BTCUSDT.P", "Binance BTCUSDT Perp"),
    ),
    (
        "coinbase",
        "BTC-USD",
        "BTC-USD Spot",
        ContractType.SPOT,
        "BTC",
        "USD",
        "USD",
        "crypto",
        ("BTC-USD", "BTCUSD Spot", "Coinbase BTC-USD"),
    ),
    (
        "binance",
        "ETHUSDT",
        "ETHUSDT Perpetual",
        ContractType.PERPETUAL,
        "ETH",
        "USDT",
        "USDT",
        "crypto",
        ("ETHUSDT Perpetual", "ETHUSDT.P"),
    ),
)

# Canonical ACTIVE seed families (doc 10 §3.1). The last entry is the Production
# correction (RF-15): V18's ESP metadata references "Embedded System / TA Resolver"
# but the prototype's visible card list omits it, so it is seeded ACTIVE here.
_RATIONALE_FAMILIES: tuple[tuple[str, list[str], list[str]], ...] = (
    (
        "Reversal / Mean Reversion",
        ["Range Reversion", "Panic Reversion", "VWAP Reversion", "Statistical Reversion"],
        ["Directional Signal", "Oversold / Overbought Zone", "Distance from Mean"],
    ),
    (
        "Trend / Directional Regime",
        ["Trend Continuation", "Direction State", "Pullback Continuation"],
        ["Color / Direction State", "Trend State", "Moving Average Slope"],
    ),
    (
        "Breakout / Volatility Expansion",
        ["Range Break", "Volume Breakout", "Momentum Expansion"],
        ["Breakout Signal", "Volume Confirmation", "Range Exit"],
    ),
    (
        "Volatility / Regime",
        ["Compression", "Expansion", "High Volatility", "Low Volatility"],
        ["Regime Label", "Volatility State", "ATR Threshold"],
    ),
    (
        "External Signal / Trade Log",
        ["Copy Trading", "Imported Record", "Trade Log"],
        ["Trade Record", "Signal Event", "External Direction"],
    ),
    (
        "Embedded System / TA Resolver",
        ["TA Resolver", "Indicator Primitive"],
        ["Numeric Series", "Indicator Output"],
    ),
)

# The 7 canonical TA resolvers seeded as trusted-active ESPs (doc 09 §3.2, DC7).
# Each: (display name, canonical key, ordered parameter types). All return a numeric series.
_ESP_TA_RESOLVERS: tuple[tuple[str, str, list[str]], ...] = (
    ("ESP_TA_SMA", "ta.sma", ["series", "int"]),
    ("ESP_TA_EMA", "ta.ema", ["series", "int"]),
    ("ESP_TA_RMA", "ta.rma", ["series", "int"]),
    ("ESP_TA_ATR", "ta.atr", ["int"]),
    ("ESP_TA_RSI", "ta.rsi", ["series", "int"]),
    ("ESP_TA_WMA", "ta.wma", ["series", "int"]),
    ("ESP_TA_VWAP", "ta.vwap", ["series"]),
)

# The canonical condition resolvers (post-V1 (b) — condition blocks; extended in (b2)).
# Each returns a boolean gate: level (above/below), edge cross (crosses_above/
# crosses_below) or range (between, two bounds). Real condition packages pin one of
# these ``cond.*`` keys in their dependency snapshot.
_ESP_COND_RESOLVERS: tuple[tuple[str, str, list[str]], ...] = (
    ("ESP_COND_ABOVE", "cond.above", ["series", "float"]),
    ("ESP_COND_BELOW", "cond.below", ["series", "float"]),
    ("ESP_COND_CROSSES_ABOVE", "cond.crosses_above", ["series", "float"]),
    ("ESP_COND_CROSSES_BELOW", "cond.crosses_below", ["series", "float"]),
    ("ESP_COND_BETWEEN", "cond.between", ["series", "float", "float"]),
)


def should_seed_dev_admin() -> bool:
    """Whether to provision the credentialless ``user_admin`` HumanUser.

    The dev Admin has NO login credential — it is reachable only through
    ``X-Actor-Id``, i.e. only under ``AUTH_MODE=dev``. In session mode it is
    both useless (nobody can log in as it) and actively harmful: it is an
    ACTIVE Admin, and first-Admin bootstrap is fail-closed "only while no
    active Admin exists", so seeding it permanently blocks a real installation
    from provisioning its first Admin without a database edit.

    The default therefore follows the runtime auth mode. ``SEED_DEV_ADMIN=1``
    forces it on (an operator explicitly wanting the impersonation fixture) and
    ``SEED_DEV_ADMIN=0`` forces it off, regardless of mode.
    """
    override = os.getenv("SEED_DEV_ADMIN", "")
    if override != "":
        return override == "1"
    return get_settings().auth_mode == "dev"


async def seed_identities(session: AsyncSession) -> None:
    """Idempotently seed the default Admin human and the system Agent.

    The Principal row is flushed before its FK-dependent HumanUser/Agent row:
    without a mapped relationship() the unit of work does not derive flush
    order from the table-level FK, so batching both adds into one flush can
    emit the child INSERT first and violate the FK on a fresh database.

    In session mode the credentialless Admin HumanUser is skipped (see
    ``should_seed_dev_admin``) while its Principal row is still created: other
    seeds FK-reference ``DEFAULT_ADMIN_ID`` as an owner, and a bare principal
    never counts toward the active-Admin total that gates bootstrap.
    """
    log = get_logger("seed")
    if not should_seed_dev_admin():
        await _ensure_admin_principal(session)
        log.info("seed.dev_admin_skipped", user_id=DEFAULT_ADMIN_ID, auth_mode="session")
    elif await session.get(HumanUser, DEFAULT_ADMIN_ID) is None:
        session.add(Principal(principal_id=DEFAULT_ADMIN_ID, principal_type=PrincipalType.HUMAN))
        await session.flush()
        session.add(
            HumanUser(
                user_id=DEFAULT_ADMIN_ID,
                username=DEFAULT_ADMIN_USERNAME,
                display_name="Default Admin",
                current_role=Role.ADMIN,
                status="active",
            )
        )
        log.info("seed.admin_created", user_id=DEFAULT_ADMIN_ID)

    if await session.get(Agent, DEFAULT_AGENT_ID) is None:
        session.add(Principal(principal_id=DEFAULT_AGENT_ID, principal_type=PrincipalType.AGENT))
        await session.flush()
        session.add(Agent(agent_id=DEFAULT_AGENT_ID, name="Alpha Agent", enabled=True))
        log.info("seed.agent_created", agent_id=DEFAULT_AGENT_ID)

    await session.flush()  # principals exist before FK-dependent dataset rows


async def seed_capabilities(session: AsyncSession) -> None:
    """Idempotently seed the seven baseline Future Dev capability slots.

    Without this the Capability Registry is empty on a fresh database, so every
    Future Dev subpage reports its key as "Not registered". Doc 22 §4/§9 requires
    the fixed V18 keys to exist as PLACEHOLDER rows (inert — a capability below
    Limited/Active accepts no command and produces no output). Delegates to the
    repository's idempotent seeder; registry rows carry no principal FK, so no
    ordering constraint applies.
    """
    await capability_repo.seed_baseline_capabilities(session)
    await session.flush()


async def _seed() -> None:
    log = get_logger("seed")
    factory = get_session_factory()
    async with factory() as session:
        # E2E golden mode deliberately SKIPS the default-Admin identity seed:
        # the E2E suite provisions its own first Admin via the
        # ENTROPIA_BOOTSTRAP_ADMIN_EMAIL signup path, which is fail-closed
        # "only while no active Admin exists" — seeding user_admin here would
        # permanently disable that bootstrap on a fresh database.
        if not SEED_E2E_GOLDEN:
            await seed_identities(session)
        await seed_capabilities(session)

        if SEED_E2E_GOLDEN:
            await _seed_e2e_golden_fixture(session, log)

        if SEED_DEMO_MARKET or SEED_DEMO_RESEARCH:
            market_revision_id = await _seed_demo_market_dataset(session, log)
            if SEED_DEMO_RESEARCH:
                await _seed_demo_research_dataset(session, log, market_revision_id)

        if SEED_ESP_TA:
            await _seed_esp_ta_resolvers(session, log)

        if SEED_RATIONALE:
            await _seed_rationale_families(session, log)

        if SEED_INSTRUMENTS:
            await _seed_instruments(session, log)

        await session.commit()
    log.info("seed.done")


# ---------------------------------------------------------------------------
# E2E golden fixture (SEED_E2E_GOLDEN=1) — V18-R2 slice R2-07.
#
# Seeds the REAL records the golden-path Playwright journey needs so a fresh
# normal user can drive Strategy -> Ready PASS -> RUN SUCCEEDED end to end:
#   * a non-Admin fixture owner (first-Admin bootstrap stays intact),
#   * an ACTIVE + APPROVED OHLCV market dataset (visible to everyone — an
#     active dataset root projects as "published") whose revision carries the
#     bar resolution AND a processed Parquet asset in object storage (the
#     engine streams bars from that asset; without it every RUN fails
#     ASSET_UNAVAILABLE),
#   * an ACTIVE + validation-PASSED + APPROVED, PUBLISHED indicator package
#     whose frozen dependency_snapshot resolves to the directional ``ta.sma``
#     canonical call (Library ``can_use`` = true for any authenticated user).
#
# Chosen over an API chain in the E2E global-setup deliberately: the API path
# needs an Admin session plus two async worker pipelines (market-data analysis,
# package validation) to converge; this direct repository seed is synchronous,
# deterministic and idempotent per title/name.
# ---------------------------------------------------------------------------

E2E_FIXTURE_OWNER_ID = "user_e2e_fixture"
E2E_MARKET_TITLE = "E2E Golden BTCUSDT 1h"
E2E_INSTRUMENT_ID = "BTCUSDT"
E2E_BAR_RESOLUTION = "1h"
E2E_INDICATOR_NAME = "E2E Golden SMA"
# Bars span 2024-01-01T00:00Z .. +1500 hours; the spec's backtest_range must
# stay inside this window.
E2E_BAR_START = "2024-01-01T00:00:00Z"
E2E_BAR_COUNT = 1500


def _e2e_golden_bars() -> list[dict[str, object]]:
    """Deterministic synthetic OHLCV bars (no randomness — reproducible seed).

    A slow sine wave around 100 gives the SMA cross real directional edges so
    the engine produces genuine entries/exits, not a flat no-trade series.
    """
    import math
    from datetime import UTC, datetime, timedelta

    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows: list[dict[str, object]] = []
    for i in range(E2E_BAR_COUNT):
        ts = start + timedelta(hours=i)
        mid = 100.0 + 10.0 * math.sin(i / 24.0) + 2.0 * math.sin(i / 5.0)
        spread = 0.6
        open_ = round(mid - 0.2, 6)
        close = round(mid + 0.2, 6)
        rows.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "open": open_,
                "high": round(max(open_, close) + spread, 6),
                "low": round(min(open_, close) - spread, 6),
                "close": close,
                "volume": 1000.0 + (i % 24) * 10.0,
            }
        )
    return rows


async def _seed_e2e_fixture_owner(session: AsyncSession) -> None:
    """Idempotently seed the non-login, non-Admin principal that owns the
    golden fixture rows (a plain USER so the bootstrap-Admin path stays open)."""
    if await session.get(HumanUser, E2E_FIXTURE_OWNER_ID) is None:
        session.add(
            Principal(principal_id=E2E_FIXTURE_OWNER_ID, principal_type=PrincipalType.HUMAN)
        )
        await session.flush()
        session.add(
            HumanUser(
                user_id=E2E_FIXTURE_OWNER_ID,
                username="e2e_fixture",
                display_name="E2E Golden Fixture",
                current_role=Role.USER,
                status="active",
            )
        )
    await session.flush()


async def _seed_e2e_golden_market(session: AsyncSession, log: object) -> None:
    """Approved market dataset + processed Parquet bar asset (idempotent by title)."""
    import io

    from sqlalchemy import select

    from entropia.infrastructure.postgres.models.market_data import MarketDatasetRevision
    from entropia.infrastructure.s3.datasets import put_processed_parquet

    existing = await session.scalar(
        select(MarketDatasetRevision).where(MarketDatasetRevision.title == E2E_MARKET_TITLE)
    )
    if existing is not None:
        return
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=E2E_FIXTURE_OWNER_ID,
        created_by_principal_id=E2E_FIXTURE_OWNER_ID,
        market_data_type=MarketDataType.OHLCV,
        payload={
            "instrument": E2E_INSTRUMENT_ID,
            "resolution": E2E_BAR_RESOLUTION,
            "fixture": "e2e_golden",
        },
        title=E2E_MARKET_TITLE,
        instrument_id=E2E_INSTRUMENT_ID,
        revision_state=MarketRevisionState.APPROVED,
        lifecycle_state="active",
    )
    # The engine's higher-timeframe validation reads the pinned revision's bar
    # resolution; the repository create has no resolution kwargs, so set the
    # columns directly on the flushed row (same transaction, same invariants).
    revision.resolution_kind = ResolutionKind.BAR
    revision.resolution_value = E2E_BAR_RESOLUTION
    await session.flush()

    import polars as pl

    buffer = io.BytesIO()
    pl.DataFrame(_e2e_golden_bars()).write_parquet(buffer)
    parquet_bytes = buffer.getvalue()
    object_key, digest = put_processed_parquet(root.entity_id, parquet_bytes)
    md_repo.add_processed_asset(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        object_key=object_key,
        content_digest=digest,
        size_bytes=len(parquet_bytes),
        row_count=E2E_BAR_COUNT,
        schema_descriptor={"columns": ["timestamp", "open", "high", "low", "close", "volume"]},
    )
    log.info(  # type: ignore[attr-defined]
        "seed.e2e_golden_market_created",
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        object_key=object_key,
    )


async def _seed_e2e_golden_indicator(session: AsyncSession, log: object) -> None:
    """Published, validation-PASSED, APPROVED indicator package pinning ta.sma
    (idempotent by the Library display name in input_contract)."""
    from sqlalchemy import select

    from entropia.infrastructure.postgres.models.packages import PackageRevision

    existing = await session.scalar(
        select(PackageRevision).where(
            PackageRevision.input_contract.op("->>")("name") == E2E_INDICATOR_NAME
        )
    )
    if existing is not None:
        return
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=E2E_FIXTURE_OWNER_ID,
        created_by_principal_id=E2E_FIXTURE_OWNER_ID,
        package_kind=PackageKind.INDICATOR,
        input_contract={
            "name": E2E_INDICATOR_NAME,
            "market": E2E_INSTRUMENT_ID,
            "timeframe": E2E_BAR_RESOLUTION,
            "params": [{"name": "length", "type": "int", "default": 20}],
        },
        output_contract={"return": "series"},
        dependency_snapshot={
            "resolved": [{"canonical_key": "ta.sma", "runtime_adapter": "python"}]
        },
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
        change_note="Seed E2E golden indicator (ta.sma) for the golden-path journey.",
    )
    log.info(  # type: ignore[attr-defined]
        "seed.e2e_golden_indicator_created",
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
    )


async def _seed_e2e_golden_fixture(session: AsyncSession, log: object) -> None:
    await _seed_e2e_fixture_owner(session)
    await _seed_e2e_golden_market(session, log)
    await _seed_e2e_golden_indicator(session, log)
    # StrategyConfig.rationale_family_id is REQUIRED — the golden strategy needs
    # at least the canonical ACTIVE families to reference.
    await _seed_rationale_families(session, log, owner_id=E2E_FIXTURE_OWNER_ID)


async def _seed_instruments(session: object, log: object) -> None:
    """Seed the canonical instrument registry idempotently (GAP-16; Master §8.1).

    Uses the FK-safe order (instrument row flushed before its alias children).
    An existing ``resolution_key`` is skipped so re-running the seed is a no-op.
    """
    for venue, symbol, display, ct, base, quote, settle, market_class, aliases in _INSTRUMENT_SEEDS:
        key = resolution_key(venue, symbol, ct)
        if await instrument_repo.get_by_resolution_key(session, key) is not None:  # type: ignore[arg-type]
            continue
        instrument = instrument_repo.create_instrument(
            session,  # type: ignore[arg-type]
            resolution_key=key,
            venue_id=venue,
            symbol=symbol,
            contract_type=ct,
            display_name=display,
            base_asset=base,
            quote_asset=quote,
            settlement_asset=settle,
            market_class=market_class,
            created_by_principal_id=DEFAULT_ADMIN_ID,
        )
        await session.flush()  # type: ignore[attr-defined]
        for alias in aliases:
            norm = normalize_alias(alias)
            if await instrument_repo.get_alias(session, norm) is not None:  # type: ignore[arg-type]
                continue
            instrument_repo.add_alias(
                session,  # type: ignore[arg-type]
                instrument_id=instrument.instrument_id,
                alias_norm=norm,
                alias_text=alias,
                created_by_principal_id=DEFAULT_ADMIN_ID,
            )
        log.info("seed.instrument_created", instrument_id=instrument.instrument_id, key=key)  # type: ignore[attr-defined]


async def _seed_demo_market_dataset(session: object, log: object) -> str:
    """Seed one ACTIVE + APPROVED market dataset so Stage 2b has a dependency.

    Behind the ``SEED_DEMO_MARKET=1`` flag. The admin principal (FK target) is
    already flushed above. Returns the approved market revision id so the demo
    research dataset can pin it.
    """
    root, revision = await md_repo.create_market_dataset(
        session,  # type: ignore[arg-type]
        owner_principal_id=DEFAULT_ADMIN_ID,
        created_by_principal_id=DEFAULT_ADMIN_ID,
        market_data_type=MarketDataType.OHLCV,
        payload={"instrument": "DEMO", "resolution": "1D"},
        title="Demo OHLCV",
        instrument_id="DEMO",
        revision_state=MarketRevisionState.APPROVED,
        lifecycle_state="active",
    )
    log.info("seed.demo_market_created", entity_id=root.entity_id)  # type: ignore[attr-defined]
    return revision.revision_id


async def _seed_demo_research_dataset(
    session: object, log: object, market_revision_id: str
) -> None:
    """Seed one research dataset linked to the demo Approved market revision.

    Behind the ``SEED_DEMO_RESEARCH=1`` flag (which also forces the demo market).
    """
    root, revision = await rd_repo.create_research_dataset(
        session,  # type: ignore[arg-type]
        owner_principal_id=DEFAULT_ADMIN_ID,
        created_by_principal_id=DEFAULT_ADMIN_ID,
        payload={"fields": ["open_interest_usd"]},
        display_name="Demo BTCUSDT Open Interest",
        category_key="open_interest",
        provider_name="Demo Provider",
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        linked_market_dataset_revision_id=market_revision_id,
        revision_state=ResearchRevisionState.DRAFT,
    )
    rd_repo.add_market_link(
        session,  # type: ignore[arg-type]
        entity_id=root.entity_id,
        market_dataset_revision_id=market_revision_id,
        revision_id=revision.revision_id,
    )
    log.info("seed.demo_research_created", entity_id=root.entity_id)  # type: ignore[attr-defined]


async def _seed_esp_ta_resolvers(session: object, log: object) -> None:
    """Seed the canonical TA + threshold-condition resolvers as trusted-active ESPs.

    Behind the ``SEED_ESP_TA=1`` flag (doc 09 §3.2, DC7). The admin principal (FK
    target) is already flushed above. Each resolver gets a System-owned ESP package
    (passed + approved revision), a resolver contract and a TRUSTED_ACTIVE registry
    row so Pre-Check can resolve it. Idempotent per key. The TA resolvers return a
    numeric series; the ``cond.*`` threshold resolvers return a boolean gate.
    """
    # R2-12: the resolver rows FK-reference the admin PRINCIPAL. Under
    # SEED_E2E_GOLDEN the identity seed is deliberately skipped (bootstrap
    # stays open), so ensure the bare Principal row exists WITHOUT creating an
    # active Admin HumanUser — the first-Admin bootstrap counts human_users,
    # never principals, so this cannot close the promotion window.
    await _ensure_admin_principal(session)
    for resolver in _ESP_TA_RESOLVERS:
        await _seed_esp_resolver(session, log, spec=resolver, return_type="series")
    for resolver in _ESP_COND_RESOLVERS:
        await _seed_esp_resolver(session, log, spec=resolver, return_type="boolean")


async def _ensure_admin_principal(session: object) -> None:
    """Idempotently ensure the admin PRINCIPAL row (FK target) exists.

    Adds ONLY the ``principals`` row — never a HumanUser — so the
    ENTROPIA_BOOTSTRAP_ADMIN_EMAIL first-signup promotion (which counts
    active Admin human_users) keeps working on a fresh E2E database.
    """
    if await session.get(Principal, DEFAULT_ADMIN_ID) is None:  # type: ignore[attr-defined]
        session.add(  # type: ignore[attr-defined]
            Principal(principal_id=DEFAULT_ADMIN_ID, principal_type=PrincipalType.HUMAN)
        )
        await session.flush()  # type: ignore[attr-defined]


async def _seed_esp_resolver(
    session: object,
    log: object,
    *,
    spec: tuple[str, str, list[str]],
    return_type: str,
) -> None:
    """Seed ONE canonical resolver (idempotent; skips a key already in the registry).

    Uses the FK-safe async ``create_package`` (root flushed before children)."""
    display_name, canonical_key, param_types = spec
    existing = await esp_repo.get_registry_by_key(session, canonical_key)  # type: ignore[arg-type]
    if existing is not None:
        return
    signature = {
        "params": [{"name": f"arg{i}", "type": t} for i, t in enumerate(param_types)],
        "return": return_type,
    }
    contract_payload = {"resolver_key": canonical_key, "signature": signature}
    _root, _detail, revision = await pkg_repo.create_package(
        session,  # type: ignore[arg-type]
        owner_principal_id=DEFAULT_ADMIN_ID,
        created_by_principal_id=DEFAULT_ADMIN_ID,
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract=contract_payload,
        output_contract={"return": return_type},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
        change_note=f"Seed canonical resolver {display_name}.",
    )
    esp_repo.add_resolver_contract(
        session,  # type: ignore[arg-type]
        entity_id=_root.entity_id,
        revision_id=revision.revision_id,
        canonical_key=canonical_key,
        signature=signature,
        runtime_adapter=RuntimeAdapter.PYTHON,
        timing_semantics="closed_bar_only",
        repaint=False,
        evidence={"test_vectors": "seed", "review": "passed"},
    )
    esp_repo.upsert_registry_entry(
        session,  # type: ignore[arg-type]
        canonical_key=canonical_key,
        package_entity_id=_root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id=DEFAULT_ADMIN_ID,
    )
    log.info("seed.esp_resolver_created", canonical_key=canonical_key)  # type: ignore[attr-defined]


async def _seed_rationale_families(
    session: object, log: object, *, owner_id: str = DEFAULT_ADMIN_ID
) -> None:
    """Seed the 6 canonical ACTIVE Rationale Families (doc 10 §3.1, RF-15).

    Behind the ``SEED_RATIONALE=1`` flag. The admin principal (FK target) is already
    flushed above. Idempotent: skips a normalized name that already has an active or
    soft-deleted (reserved) family. Uses the FK-safe async ``create_family`` (root
    flushed before children).
    """
    for ordinal, (display_name, subfamilies, output_types) in enumerate(_RATIONALE_FAMILIES):
        norm = normalized_name(display_name)
        existing = await rationale_repo.find_active_or_reserved_by_name(session, norm)  # type: ignore[arg-type]
        if existing is not None:
            continue
        count = await rationale_repo.count_family_roots(session)  # type: ignore[arg-type]
        root, _detail, _revision = await rationale_repo.create_family(
            session,  # type: ignore[arg-type]
            owner_principal_id=owner_id,
            created_by_principal_id=owner_id,
            display_name=display_name,
            normalized_name=norm,
            subfamilies=subfamilies,
            compatible_output_types=output_types,
            display_color=pick_color(count),
            change_note=f"Seed canonical Rationale Family {display_name} (ordinal {ordinal}).",
        )
        log.info("seed.rationale_family_created", entity_id=root.entity_id)  # type: ignore[attr-defined]


def run() -> None:
    configure_logging()
    asyncio.run(_seed())


if __name__ == "__main__":
    run()
