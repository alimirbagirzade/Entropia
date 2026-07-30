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
from entropia.apps.api.deps import TransactionBoundaryMiddleware
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
    auth,
    backtest,
    capability,
    create_package,
    esp,
    health,
    identity,
    instrument,
    library,
    mainboard,
    manual,
    market_data,
    meta,
    metric_profile,
    metrics,
    package_import,
    rationale,
    readiness,
    research_data,
    result_export,
    results_history,
    sharing,
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


# --- CORS allowlists (I-14) --------------------------------------------------
# The origin list was already narrow (env-driven, no wildcard), but methods and
# headers were ``["*"]`` while ``allow_credentials=True``. Both are now closed
# enumerations of what this API actually serves.
#
# METHODS: the five verbs the routers declare (GET/POST/PATCH/PUT/DELETE), plus
# HEAD (Starlette mints one per GET route — ``routing.py``) and OPTIONS (the
# preflight verb itself). This currently matches what ``"*"`` expands to, so it
# is a PIN, not a reduction: ``"*"`` means "whatever ``starlette.ALL_METHODS``
# holds after any upgrade", this means exactly these seven and nothing else.
CORS_ALLOWED_METHODS = ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT")

# HEADERS: this IS the reduction. ``allow_headers=["*"]`` makes Starlette mirror
# back whatever ``Access-Control-Request-Headers`` the caller asks for, so an
# allowed origin got blanket preflight approval for every header name. Each entry
# below is a header the backend genuinely reads; anything else now fails
# preflight with 400 "Disallowed CORS headers".
CORS_ALLOWED_HEADERS = (
    "Authorization",  # deps.py — Bearer session token / service-line token
    "Content-Type",  # JSON bodies + multipart uploads (also CORS-safelisted)
    "If-Match",  # OCC dual-token — shared/concurrency.py::reconcile_occ_tokens
    "Idempotency-Key",  # application/idempotency.py::run_idempotent
    "X-Actor-Id",  # deps.py::ACTOR_ID_HEADER (dev profile) + rate-limit key
    "X-Request-Version",  # OCC — routes/create_package.py
    "X-Registry-Version",  # OCC — routes/esp.py, routes/instrument.py
    "X-Request-Id",  # context.py — caller-supplied trace id, echoed back
    "X-Correlation-Id",  # context.py — caller-supplied correlation id
    "Last-Event-ID",  # sse.py::_requested_cursor — SSE reconnect cursor
)


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

    # Middleware stack (added inner -> outer): transaction boundary innermost
    # (commits the request session BEFORE the response leaves the app — closes
    # the create->immediate-read race), CORS, then rate limiting (a 429 is shed
    # before route work), metrics (counts every response incl. 429), security
    # headers (ride EVERY response), and request context outermost.
    app.add_middleware(TransactionBoundaryMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=list(CORS_ALLOWED_METHODS),
        allow_headers=list(CORS_ALLOWED_HEADERS),
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
    app.include_router(auth.router, prefix=base)
    app.include_router(identity.router, prefix=base)
    app.include_router(admin_panel.router, prefix=base)
    app.include_router(trash.router, prefix=base)
    app.include_router(audit.router, prefix=base)
    app.include_router(market_data.router, prefix=base)
    app.include_router(research_data.router, prefix=base)
    app.include_router(esp.router, prefix=base)
    app.include_router(instrument.router, prefix=base)
    app.include_router(rationale.router, prefix=base)
    app.include_router(create_package.router, prefix=base)
    app.include_router(library.router, prefix=base)
    app.include_router(package_import.router, prefix=base)
    app.include_router(sharing.router, prefix=base)
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
