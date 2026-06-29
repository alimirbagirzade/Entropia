"""Canonical application error model and the API error envelope.

Every API failure returns the same shape (Module 19 API contract):

    { "error": { "code", "message", "details", "request_id", "correlation_id" } }

Domain code raises ``AppError`` subclasses; the API layer translates them into
HTTP responses with the right status code. Stack traces are never exposed.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all expected, typed application failures."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or []
        super().__init__(self.message)


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422
    message = "The request failed validation."


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404
    message = "The requested resource was not found."


class UnauthenticatedError(AppError):
    code = "UNAUTHENTICATED"
    http_status = 401
    message = "Authentication is required."


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    http_status = 403
    message = "You do not have permission to perform this action."


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = 409
    message = "The request conflicts with the current state."


class StaleRevisionError(ConflictError):
    """Optimistic-concurrency failure (ETag/If-Match or expected_* token)."""

    code = "STALE_REVISION"
    message = "The resource was modified by someone else. Refresh and retry."


class CapabilityNotActiveError(ForbiddenError):
    """Future Dev / activation-gated capability invoked while inactive."""

    code = "CAPABILITY_NOT_ACTIVE"
    message = "This capability is not active."


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    http_status = 503
    message = "A dependency is currently unavailable."
