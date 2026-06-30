"""FastAPI application factory — the API process entrypoint (Module 20 §2,§3).

Route handlers only parse the request, resolve actor context, and call an
application command/query. No SQL, queue enqueue, object-storage path building,
or business policy lives here. Long-running work becomes a job, never inline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from entropia import __version__
from entropia.apps.api.context import RequestContextMiddleware
from entropia.apps.api.errors import install_exception_handlers
from entropia.apps.api.routes import (
    audit,
    create_package,
    esp,
    health,
    identity,
    library,
    market_data,
    meta,
    rationale,
    research_data,
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
    yield
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-Correlation-Id", "ETag"],
    )
    app.add_middleware(RequestContextMiddleware)

    install_exception_handlers(app)

    base = settings.api_base_path
    app.include_router(health.router, prefix=base)
    app.include_router(meta.router, prefix=base)
    app.include_router(sse_router, prefix=base)
    app.include_router(identity.router, prefix=base)
    app.include_router(trash.router, prefix=base)
    app.include_router(audit.router, prefix=base)
    app.include_router(market_data.router, prefix=base)
    app.include_router(research_data.router, prefix=base)
    app.include_router(esp.router, prefix=base)
    app.include_router(rationale.router, prefix=base)
    app.include_router(create_package.router, prefix=base)
    app.include_router(library.router, prefix=base)

    return app


app = create_app()
