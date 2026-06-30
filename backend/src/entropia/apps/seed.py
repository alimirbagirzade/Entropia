"""Seed baseline identities for local development.

    python -m entropia.apps.seed

Creates (idempotently) a default Admin human user and the non-login system
Agent. Intended for local/staging bootstrap only — production identity
provisioning is part of the deferred security/IdP decision.
"""

from __future__ import annotations

import asyncio
import os

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.research_data.enums import ResearchRevisionState, UsageScope
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.models import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo

DEFAULT_ADMIN_ID = os.getenv("SEED_ADMIN_ID", "user_admin")
DEFAULT_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
DEFAULT_AGENT_ID = os.getenv("SEED_AGENT_ID", "agent_alpha")
SEED_DEMO_MARKET = os.getenv("SEED_DEMO_MARKET", "0") == "1"
SEED_DEMO_RESEARCH = os.getenv("SEED_DEMO_RESEARCH", "0") == "1"
SEED_ESP_TA = os.getenv("SEED_ESP_TA", "0") == "1"

# The 7 canonical TA resolvers seeded as trusted-active ESPs (doc 09 §3.2, DC7).
# Each: (canonical key, ordered parameter types). All return a numeric series.
_ESP_TA_RESOLVERS: tuple[tuple[str, str, list[str]], ...] = (
    ("ESP_TA_SMA", "ta.sma", ["series", "int"]),
    ("ESP_TA_EMA", "ta.ema", ["series", "int"]),
    ("ESP_TA_RMA", "ta.rma", ["series", "int"]),
    ("ESP_TA_ATR", "ta.atr", ["int"]),
    ("ESP_TA_RSI", "ta.rsi", ["series", "int"]),
    ("ESP_TA_WMA", "ta.wma", ["series", "int"]),
    ("ESP_TA_VWAP", "ta.vwap", ["series"]),
)


async def _seed() -> None:
    log = get_logger("seed")
    factory = get_session_factory()
    async with factory() as session:
        if await session.get(HumanUser, DEFAULT_ADMIN_ID) is None:
            session.add(
                Principal(principal_id=DEFAULT_ADMIN_ID, principal_type=PrincipalType.HUMAN)
            )
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
            session.add(
                Principal(principal_id=DEFAULT_AGENT_ID, principal_type=PrincipalType.AGENT)
            )
            session.add(Agent(agent_id=DEFAULT_AGENT_ID, name="Alpha Agent", enabled=True))
            log.info("seed.agent_created", agent_id=DEFAULT_AGENT_ID)

        await session.flush()  # principals exist before FK-dependent dataset rows

        if SEED_DEMO_MARKET or SEED_DEMO_RESEARCH:
            market_revision_id = await _seed_demo_market_dataset(session, log)
            if SEED_DEMO_RESEARCH:
                await _seed_demo_research_dataset(session, log, market_revision_id)

        if SEED_ESP_TA:
            await _seed_esp_ta_resolvers(session, log)

        await session.commit()
    log.info("seed.done")


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
    """Seed the 7 canonical TA resolvers as trusted-active ESPs (doc 09 §3.2, DC7).

    Behind the ``SEED_ESP_TA=1`` flag. The admin principal (FK target) is already
    flushed above. Each resolver gets a System-owned ESP package (passed +
    approved revision), a resolver contract and a TRUSTED_ACTIVE registry row so
    Pre-Check can resolve it. Idempotent: skips a key that already has a registry
    entry. Uses the FK-safe async ``create_package`` (root flushed before children).
    """
    for display_name, canonical_key, param_types in _ESP_TA_RESOLVERS:
        existing = await esp_repo.get_registry_by_key(session, canonical_key)  # type: ignore[arg-type]
        if existing is not None:
            continue
        signature = {
            "params": [{"name": f"arg{i}", "type": t} for i, t in enumerate(param_types)],
            "return": "series",
        }
        contract_payload = {"resolver_key": canonical_key, "signature": signature}
        _root, _detail, revision = await pkg_repo.create_package(
            session,  # type: ignore[arg-type]
            owner_principal_id=DEFAULT_ADMIN_ID,
            created_by_principal_id=DEFAULT_ADMIN_ID,
            package_kind=PackageKind.EMBEDDED_SYSTEM,
            input_contract=contract_payload,
            output_contract={"return": "series"},
            dependency_snapshot={},
            visibility_scope=VisibilityScope.SYSTEM,
            validation_state=PackageValidationState.PASSED,
            approval_state=ApprovalState.APPROVED,
            change_note=f"Seed canonical TA resolver {display_name}.",
        )
        esp_repo.add_resolver_contract(
            session,  # type: ignore[arg-type]
            entity_id=_root.entity_id,
            revision_id=revision.revision_id,
            canonical_key=canonical_key,
            signature=signature,
            runtime_adapter=RuntimeAdapter.PINE_V5,
            timing_semantics="closed_bar_only",
            repaint=False,
            evidence={"test_vectors": "seed", "review": "passed"},
        )
        esp_repo.upsert_registry_entry(
            session,  # type: ignore[arg-type]
            canonical_key=canonical_key,
            package_entity_id=_root.entity_id,
            runtime_adapter=RuntimeAdapter.PINE_V5,
            trust_state=ResolverTrustState.TRUSTED_ACTIVE,
            trusted_active_revision_id=revision.revision_id,
            updated_by_principal_id=DEFAULT_ADMIN_ID,
        )
        log.info("seed.esp_ta_created", canonical_key=canonical_key)  # type: ignore[attr-defined]


def run() -> None:
    configure_logging()
    asyncio.run(_seed())


if __name__ == "__main__":
    run()
