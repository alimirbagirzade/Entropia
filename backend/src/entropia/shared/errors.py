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


class AccessDeniedError(ForbiddenError):
    """Authenticated actor lacks permission for this resource/action."""

    code = "ACCESS_DENIED"
    message = "You do not have access to this resource."


class LastAdminProtectedError(ConflictError):
    """The last active Admin cannot be demoted or deactivated."""

    code = "LAST_ADMIN_PROTECTED"
    http_status = 422
    message = "The last active administrator cannot be demoted or deactivated."


class AgentRoleNotAssignableError(ValidationError):
    """Agent is a non-login system actor; it is not an assignable human role."""

    code = "AGENT_ROLE_NOT_ASSIGNABLE"
    message = "The Agent role cannot be assigned to a human user."


class RoleContextStaleError(ConflictError):
    """A request used a role context that has since changed."""

    code = "ROLE_CONTEXT_STALE"
    message = "Your role changed. Refresh and retry."


class IdempotencyConflictError(ConflictError):
    """Same idempotency key reused with a different request payload."""

    code = "IDEMPOTENCY_KEY_CONFLICT"
    message = "This idempotency key was already used with a different request."


class ApprovalRequiresAdmin(ForbiddenError):
    """Only the Admin role may approve a revision (Market Data §, CR-02)."""

    code = "APPROVAL_REQUIRES_ADMIN"
    message = "Approving this revision requires the Admin role."


class MappingReviewRequired(ConflictError):
    """An essential canonical field is unmapped or ambiguous; manual review needed."""

    code = "MAPPING_REVIEW_REQUIRED"
    http_status = 422
    message = "Schema mapping needs review before a revision can be created."


class TimezoneRequired(ValidationError):
    """A custom timezone mode was selected without an IANA timezone identifier."""

    code = "TIMEZONE_REQUIRED"
    message = "A custom timezone mode requires an IANA timezone identifier."


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    http_status = 503
    message = "A dependency is currently unavailable."
