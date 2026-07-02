"""FastAPI application factory — the API process entrypoint (Module 20 §2,§3).

Route handlers only parse the request, resolve actor context, and call an
application command/query. No SQL, queue enqueue, object-storage path building,
or business policy lives here. Long-running work becomes a job, never inline.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from entropia import __version__
from entropia.apps.api import sse
from entropia.apps.api.context import RequestContextMiddleware
from entropia.apps.api.errors import install_exception_handlers
from entropia.apps.api.hardening import (
    MetricsMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from entropia.apps.api.routes import (
    admin_panel,
    agent_lab,
    allocation,
    audit,
    backtest,
    capability,
    create_package,
    esp,
    health,
    identity,
    library,
    mainboard,
    manual,
    market_data,
    meta,
    metric_profile,
    metrics,
    rationale,
    readiness,
    research_data,
    result_export,
    results_history,
    strategy,
    trade_log,
    trading_signal,
    trash,
)
from entropia.apps.api.sse import router as sse_router
from entropia.config import get_settings
from entropia.infrastructure.observability import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("api")
    settings = get_settings()
    log.info("api.startup", environment=settings.environment, version=__version__)
    # Outbox -> SSE fan-out (Module 20 §10): a per-process, loss-tolerant tail.
    stop_poller = asyncio.Event()
    poller = asyncio.create_task(
        sse.run_outbox_poller(stop_poller, poll_interval_seconds=settings.sse_poll_interval_seconds)
    )
    yield
    stop_poller.set()
    await poller
    log.info("api.shutdown")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Entropia V18 API",
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Middleware stack (added inner -> outer): CORS, then rate limiting (a 429
    # is shed before route work), metrics (counts every response incl. 429),
    # security headers (ride EVERY response), and request context outermost.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-Correlation-Id", "ETag"],
    )
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    install_exception_handlers(app)

    base = settings.api_base_path
    app.include_router(health.router, prefix=base)
    app.include_router(meta.router, prefix=base)
    app.include_router(metrics.router, prefix=base)
    app.include_router(sse_router, prefix=base)
    app.include_router(identity.router, prefix=base)
    app.include_router(admin_panel.router, prefix=base)
    app.include_router(trash.router, prefix=base)
    app.include_router(audit.router, prefix=base)
    app.include_router(market_data.router, prefix=base)
    app.include_router(research_data.router, prefix=base)
    app.include_router(esp.router, prefix=base)
    app.include_router(rationale.router, prefix=base)
    app.include_router(create_package.router, prefix=base)
    app.include_router(library.router, prefix=base)
    app.include_router(mainboard.router, prefix=base)
    app.include_router(strategy.router, prefix=base)
    app.include_router(trading_signal.router, prefix=base)
    app.include_router(trade_log.router, prefix=base)
    app.include_router(allocation.router, prefix=base)
    app.include_router(readiness.router, prefix=base)
    app.include_router(backtest.router, prefix=base)
    app.include_router(results_history.router, prefix=base)
    app.include_router(metric_profile.router, prefix=base)
    app.include_router(result_export.router, prefix=base)
    app.include_router(agent_lab.router, prefix=base)
    app.include_router(manual.router, prefix=base)
    app.include_router(capability.router, prefix=base)

    return app


app = create_app()
