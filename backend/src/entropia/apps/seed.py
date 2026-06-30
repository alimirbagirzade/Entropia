"""Seed baseline identities for local development.

    python -m entropia.apps.seed

Creates (idempotently) a default Admin human user and the non-login system
Agent. Intended for local/staging bootstrap only — production identity
provisioning is part of the deferred security/IdP decision.
"""

from __future__ import annotations

import asyncio
import os

from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.models import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.repositories import market_data as md_repo

DEFAULT_ADMIN_ID = os.getenv("SEED_ADMIN_ID", "user_admin")
DEFAULT_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
DEFAULT_AGENT_ID = os.getenv("SEED_AGENT_ID", "agent_alpha")
SEED_DEMO_MARKET = os.getenv("SEED_DEMO_MARKET", "0") == "1"


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

        if SEED_DEMO_MARKET:
            await _seed_demo_market_dataset(session, log)

        await session.commit()
    log.info("seed.done")


async def _seed_demo_market_dataset(session: object, log: object) -> None:
    """Seed one ACTIVE + APPROVED market dataset so Stage 2b has a dependency.

    Behind the ``SEED_DEMO_MARKET=1`` flag. The admin principal (FK target) is
    already flushed above.
    """
    root, revision = md_repo.create_market_dataset(
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
    del revision


def run() -> None:
    configure_logging()
    asyncio.run(_seed())


if __name__ == "__main__":
    run()
