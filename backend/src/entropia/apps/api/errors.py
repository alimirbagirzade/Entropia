"""Translate exceptions into the canonical error envelope (Module 19).

Never leaks stack traces or internal paths. AppError subclasses map to their
declared http_status; unexpected exceptions become a generic 500.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from entropia.infrastructure.observability import get_logger
from entropia.shared.errors import AppError, ErrorCategory
from entropia.shared.responses import ErrorBody, ErrorResponse

log = get_logger("api.errors")


@dataclass(frozen=True, slots=True)
class _Recovery:
    """The recovery block of one error response (doc 01 §11.2, doc 04 §11.1).

    Grouped into a value object so ``_envelope`` keeps a readable signature: an
    ``AppError`` supplies it directly, and framework-raised responses derive a
    conservative one from the HTTP status alone.
    """

    category: ErrorCategory = ErrorCategory.INTERNAL
    retryable: bool = False
    suggested_action: str | None = None
    remediation: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    field_path: str | None = None

    @classmethod
    def from_app_error(cls, exc: AppError) -> _Recovery:
        return cls(
            category=exc.category,
            retryable=exc.retryable,
            suggested_action=exc.suggested_action,
            remediation=exc.remediation,
            scope_type=exc.scope_type,
            scope_id=exc.scope_id,
            field_path=exc.field_path,
        )


# Framework-raised responses (unmatched route, wrong method, an explicit
# ``raise HTTPException``) carry no domain classification, so the category is
# derived from the status family. Anything unlisted stays ``internal`` and not
# retryable — a failure is never advertised as retryable on a guess.
_STATUS_CATEGORIES: dict[int, ErrorCategory] = {
    400: ErrorCategory.VALIDATION,
    401: ErrorCategory.AUTHORIZATION,
    403: ErrorCategory.AUTHORIZATION,
    404: ErrorCategory.NOT_FOUND,
    405: ErrorCategory.VALIDATION,
    409: ErrorCategory.CONFLICT,
    415: ErrorCategory.VALIDATION,
    422: ErrorCategory.VALIDATION,
    429: ErrorCategory.RATE_LIMIT,
}


def _status_recovery(status: int) -> _Recovery:
    category = _STATUS_CATEGORIES.get(status, ErrorCategory.INTERNAL)
    if category is ErrorCategory.RATE_LIMIT:
        return _Recovery(category=category, retryable=True, suggested_action="retry_later")
    return _Recovery(category=category)


def _envelope(
    request: Request,
    *,
    code: str,
    message: str,
    details: list[dict[str, object]] | None,
    status: int,
    recovery: _Recovery,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or [],
            request_id=getattr(request.state, "request_id", None),
            correlation_id=getattr(request.state, "correlation_id", None),
            category=recovery.category,
            retryable=recovery.retryable,
            suggested_action=recovery.suggested_action,
            remediation=recovery.remediation,
            scope_type=recovery.scope_type,
            scope_id=recovery.scope_id,
            field_path=recovery.field_path,
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


def _publish_error_schema(app: FastAPI) -> None:
    """Put the error envelope into ``components.schemas``.

    Error responses are produced by these exception handlers, not by endpoints, so
    no route declares ``ErrorResponse`` as a response model and FastAPI would leave
    the one shape every failure returns out of the schema entirely. Registering it
    here lands the contract in the committed ``docs/openapi.json`` snapshot, where
    the drift guard reviews any future change to it. Route entries are untouched.
    """
    build_schema = app.openapi

    def openapi_with_error_envelope() -> dict[str, Any]:
        schema = build_schema()
        components: dict[str, Any] = schema.setdefault("components", {}).setdefault("schemas", {})
        envelope = ErrorResponse.model_json_schema(
            ref_template="#/components/schemas/{model}",
        )
        components.update(envelope.pop("$defs", {}))
        components["ErrorResponse"] = envelope
        return schema

    app.openapi = openapi_with_error_envelope  # type: ignore[method-assign]


def install_exception_handlers(app: FastAPI) -> None:
    _publish_error_schema(app)

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope(
            request,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status=exc.http_status,
            recovery=_Recovery.from_app_error(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e.get("loc", [])), "issue": e.get("msg", "")}
            for e in exc.errors()
        ]
        # A schema rejection names the offending field only when exactly one field
        # failed; with several, ``details`` carries them all and ``field_path`` stays
        # null rather than arbitrarily picking one.
        field_path = str(details[0]["field"]) if len(details) == 1 else None
        return _envelope(
            request,
            code="VALIDATION_ERROR",
            message="The request failed validation.",
            details=details,
            status=422,
            recovery=_Recovery(
                category=ErrorCategory.VALIDATION,
                suggested_action="correct_request_payload",
                field_path=field_path,
            ),
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
            recovery=_status_recovery(exc.status_code),
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
            recovery=_Recovery(category=ErrorCategory.INTERNAL),
        )
