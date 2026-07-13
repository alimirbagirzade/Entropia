"""Translate exceptions into the canonical error envelope (Module 19).

Never leaks stack traces or internal paths. AppError subclasses map to their
declared http_status; unexpected exceptions become a generic 500.
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from entropia.infrastructure.observability import get_logger
from entropia.shared.errors import AppError
from entropia.shared.responses import ErrorBody, ErrorResponse

log = get_logger("api.errors")


def _envelope(
    request: Request,
    *,
    code: str,
    message: str,
    details: list[dict[str, object]] | None,
    status: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or [],
            request_id=getattr(request.state, "request_id", None),
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def _status_labels(status: int) -> tuple[str, str]:
    """Derive a canonical ``code`` and default ``message`` from an HTTP status.

    404 -> ("NOT_FOUND", "Not Found"); 405 -> ("METHOD_NOT_ALLOWED", ...).
    Unknown/custom codes fall back to a stable ``HTTP_<status>`` code.
    """
    try:
        phrase = HTTPStatus(status).phrase
    except ValueError:
        return f"HTTP_{status}", "The request could not be completed."
    code = "".join(ch if ch.isalnum() else "_" for ch in phrase).upper()
    return code, phrase


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope(
            request, code=exc.code, message=exc.message, details=exc.details, status=exc.http_status
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e.get("loc", [])), "issue": e.get("msg", "")}
            for e in exc.errors()
        ]
        return _envelope(
            request,
            code="VALIDATION_ERROR",
            message="The request failed validation.",
            details=details,
            status=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Framework-raised responses (404 unmatched route, 405 wrong method) and any
        # explicit ``raise HTTPException`` must use the canonical envelope too, not
        # Starlette's default ``{"detail": ...}`` shape. Preserve carried headers
        # (405 ``Allow``, 401 ``WWW-Authenticate``, ...) exactly as the default would.
        code, phrase = _status_labels(exc.status_code)
        message = exc.detail if isinstance(exc.detail, str) and exc.detail else phrase
        return _envelope(
            request,
            code=code,
            message=message,
            details=None,
            status=exc.status_code,
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        return _envelope(
            request,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            details=[],
            status=500,
        )
