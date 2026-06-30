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


class DependencyBlocked(ConflictError):
    """A required upstream dependency is missing/inactive (Research Data §10).

    Raised when a research dataset revision has no linked ACTIVE+APPROVED market
    dataset revision, or the linked market revision is inactive/deleted/deprecated.
    """

    code = "DEPENDENCY_BLOCKED"
    message = "An Approved, active Market Data revision must be linked first."


class UsageScopeForbidden(ForbiddenError):
    """A requested consumption is not permitted by the revision's usage scope
    (Research Data §9.3 matrix, §10). e.g. Agent-Research-Only used in a backtest
    evidence bundle, or raw Feature-Input-Only bound directly to a strategy."""

    code = "USAGE_SCOPE_FORBIDDEN"
    message = "This dataset's usage scope does not permit the requested use."


class TimePolicyInvalid(ValidationError):
    """The event/available time policy is unparseable, undocumented, or unsafe
    (Research Data §10). e.g. delay not positive/parseable, custom rule
    undocumented, timezone conversion invalid, event semantics incomplete."""

    code = "TIME_POLICY_INVALID"
    message = "The time policy is invalid; available time cannot be validated."


class FieldMeaningInsufficient(ValidationError):
    """Field meaning was not enriched to field-level semantic metadata
    (Research Data §8.3, §10). A single prose paragraph is insufficient."""

    code = "FIELD_MEANING_INSUFFICIENT"
    message = "Field meaning must define field-level semantic metadata."


class CustomCategoryRequired(ValidationError):
    """Data Category = Other/Custom was chosen without a non-empty custom value
    (Research Data §5.1, §10). No silent 'Custom Research Data' fallback."""

    code = "CUSTOM_CATEGORY_REQUIRED"
    message = "Enter a custom category for Other / Custom."


class ClientLegacyTypeRejected(ValidationError):
    """A legacy/invalid client package type was supplied (ESP doc 09 §14, CR-01).

    Package types are only ``strategy``/``indicator``/``condition``/
    ``embedded_system``; ``trading_signal`` and ``trade_log`` are external
    Mainboard working objects and are never modeled as a package.
    """

    code = "CLIENT_LEGACY_TYPE_REJECTED"
    message = "That package type is not supported."


class ResolverSignatureMismatch(ValidationError):
    """A resolver with the same key exists but its canonical signature is not
    compatible with the parsed call (ESP doc 09 §9.3, §11.1). Name-only matching
    is never accepted."""

    code = "RESOLVER_SIGNATURE_MISMATCH"
    message = "The resolver signature is not compatible with this call."


class ResolverAdapterIncompatible(ConflictError):
    """The resolver is trusted, but no approved runtime adapter is compatible
    with the requested target runtime (ESP doc 09 §7.1, §11.1)."""

    code = "RESOLVER_ADAPTER_INCOMPATIBLE"
    message = "No approved runtime adapter is compatible with the target runtime."


class ResolverNotResolved(NotFoundError):
    """No trusted active resolver revision matched this dependency (ESP doc 09
    §7.1 "Missing resolver warning", §9.2). The conversion branch is blocked
    (PRECHECK_BLOCKED) until a compatible revision is approved."""

    code = "RESOLVER_NOT_RESOLVED"
    message = "No trusted Embedded System Package matched this dependency."


class ResolverContractInvalid(ValidationError):
    """The resolver contract failed typed schema validation (ESP doc 09 §11.1)."""

    code = "RESOLVER_CONTRACT_INVALID"
    message = "The resolver contract is invalid."


class ResolverRegistryConflict(ConflictError):
    """Optimistic-concurrency failure on a registry mutation (ESP doc 09 §9.4,
    §6 "Expected head revision"). The expected registry/head token no longer
    matches; no silent last-write-wins activation/deprecation is performed."""

    code = "RESOLVER_REGISTRY_CONFLICT"
    message = "This resolver changed while you were reviewing it. Reload and retry."


class DeletePolicyBlocked(ConflictError):
    """Soft-delete of an active trusted resolver is blocked; deprecate first
    (ESP doc 09 §9.5, §14, §7.1 "Error - blocked delete")."""

    code = "DELETE_POLICY_BLOCKED"
    message = "This resolver is active in the registry. Deprecate it before deletion."


class RationaleFamilyNameRequired(ValidationError):
    """A Rationale Family name was blank/whitespace-only (doc 10 §10.1)."""

    code = "RATIONALE_FAMILY_NAME_REQUIRED"
    message = "Enter a shared semantic Rationale Family name."


class RationaleFamilyNameTooLong(ValidationError):
    """A Rationale Family name exceeded 120 visible characters (doc 10 §10.1)."""

    code = "RATIONALE_FAMILY_NAME_TOO_LONG"
    message = "A Rationale Family name must be 2-120 visible characters."


class RationaleFamilyInvalidText(ValidationError):
    """Family text contained unsafe control characters (doc 10 §10.1)."""

    code = "RATIONALE_FAMILY_INVALID_TEXT"
    message = "Paste plain visible text and retry."


class RationaleFamilyMetadataLimit(ValidationError):
    """Subfamily / compatible-output list exceeded count/length caps (doc 10 §10.1)."""

    code = "RATIONALE_FAMILY_METADATA_LIMIT"
    message = "Split or trim the list; keep meaningful distinct values."


class RationaleFamilyNameConflict(ConflictError):
    """An ACTIVE family already uses this normalized name (doc 10 §10.1, RF-07)."""

    code = "RATIONALE_FAMILY_NAME_CONFLICT"
    message = "A Rationale Family with this name already exists."


class RationaleFamilyNameReserved(ConflictError):
    """A soft-deleted family reserves this normalized name (doc 10 §10.1, RF-08).

    Recovery: restore/rename the existing family from Trash (Admin) or choose a
    different name.
    """

    code = "RATIONALE_FAMILY_NAME_RESERVED"
    message = "This name is reserved by a deleted Rationale Family. Choose a different name."


class RationaleFamilyConflict(ConflictError):
    """Optimistic-concurrency failure on a family revision (doc 10 §8.3, §10.1,
    RF-03). The expected head revision/ETag is stale; no last-write-wins overwrite
    is applied."""

    code = "RATIONALE_FAMILY_CONFLICT"
    message = "This Family changed after you opened it. Reload the current revision and reapply."


class RationaleFamilyNotActive(ConflictError):
    """A soft-deleted family was selected for a new assignment (doc 10 §10.2).

    Historical snapshots remain valid; new selection must use an ACTIVE family or
    Unassigned. Restore is Admin-only from Trash.
    """

    code = "RATIONALE_FAMILY_NOT_ACTIVE"
    message = "Select an active Rationale Family or Unassigned; this Family is deleted."


class PackageRationaleAssignmentConflict(ConflictError):
    """An atomic assignment batch referenced a stale package/table version
    (doc 10 §8.4, §10.2, RF-09). No partial Package revisions are created — the
    whole batch is rejected."""

    code = "PACKAGE_RATIONALE_ASSIGNMENT_CONFLICT"
    message = "One or more Packages changed after this table was loaded. No assignments were saved."


class PackageNotFound(NotFoundError):
    """A rationale-assignment row referenced a missing package root (doc 10 §10.2)."""

    code = "PACKAGE_NOT_FOUND"
    message = "The referenced package was not found."


class LifecycleBlocked(ConflictError):
    """An operation is blocked by the target's current lifecycle/deletion state
    (doc 10 §10.2 "PACKAGE_NOT_FOUND or LIFECYCLE_BLOCKED")."""

    code = "LIFECYCLE_BLOCKED"
    message = "This object's current state does not permit the requested change."


class PackageRequestNotFound(NotFoundError):
    """A Create-Package request id did not resolve (doc 06 §9.1, doc 07 §10.1)."""

    code = "PACKAGE_REQUEST_NOT_FOUND"
    message = "The package request was not found."


class EmptySource(ValidationError):
    """The request body was blank/whitespace-only (doc 06 §4.4, doc 07 §5.1)."""

    code = "EMPTY_SOURCE"
    message = "Paste code or describe the package to create before continuing."


class SourceLanguageMismatch(ValidationError):
    """The selected source language is absent/present against the creation mode,
    conflicts with the detected syntax, or 'Other' has no label (doc 06 §11, §4.2).
    No silent auto-rewrite is performed."""

    code = "SOURCE_LANGUAGE_MISMATCH"
    message = "Select the correct source language for this code request."


class OutputContractInvalid(ValidationError):
    """The output contract kind is missing or incompatible with the package type
    (doc 06 §4.3, §11). Even a passed Pre-Check cannot bypass this."""

    code = "OUTPUT_CONTRACT_INVALID"
    message = "The output contract is not valid for this package type."


class RuntimeUnavailable(ValidationError):
    """The target runtime is not a registered, active adapter (doc 06 §4.2, §11).

    V1 exposes only the Python runtime adapter; PHP/other are Future-Dev.
    """

    code = "RUNTIME_UNAVAILABLE"
    message = "Select a registered, active target runtime."


class PrecheckBlocked(ConflictError):
    """A code request was sent while its current Pre-Check is BLOCKED (doc 06 §5,
    doc 07 §9.3, PC-13). Conversion cannot start until a compatible trusted ESP
    resolver exists and Pre-Check is re-run."""

    code = "PRECHECK_BLOCKED"
    message = "Conversion is blocked because a required dependency has no trusted resolver."


class PrecheckStale(ConflictError):
    """A code request was sent while its Pre-Check is stale — the source, runtime,
    output contract, dependency context or the resolver registry changed after the
    scan (doc 06 §8.5, doc 07 §4, PC-09). Re-run Pre-Check first."""

    code = "PRECHECK_STALE"
    message = "Pre-Check is stale because the context or resolver registry changed. Re-run it."


class PrecheckAlreadyRunning(ConflictError):
    """A second Pre-Check was requested while one is already in flight for the same
    context (doc 07 §8.1). The in-flight scan is reused; no duplicate job is made."""

    code = "PRECHECK_ALREADY_RUNNING"
    message = "A Pre-Check is already running for this request."


class RequestVersionConflict(ConflictError):
    """Optimistic-concurrency failure on a package request: another actor advanced
    the request head (``expected_request_version`` stale, doc 07 §8.1, §9.4)."""

    code = "REQUEST_VERSION_CONFLICT"
    message = "This request changed while you were working. Reload the current version and retry."


class CandidateNotReady(ConflictError):
    """Create Draft Package was called before a candidate is ready (doc 06 §7).

    The request must be in ``candidate_ready`` (a non-stale, succeeded candidate).
    """

    code = "CANDIDATE_NOT_READY"
    message = "No ready candidate exists for this request yet."


class CandidateStale(ConflictError):
    """The candidate hash supplied to Create Draft Package no longer matches the
    request's current candidate (doc 06 §7, §13). Review the current candidate."""

    code = "CANDIDATE_STALE"
    message = "This candidate is stale. Review the current candidate and retry."


class DependencyUnresolved(ConflictError):
    """A draft/approval was attempted while a pinned dependency is unresolved
    (doc 06 §7, §11). The dependency snapshot must be resolved and non-stale."""

    code = "DEPENDENCY_UNRESOLVED"
    message = "A required dependency is unresolved. Re-run Pre-Check and try again."


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    http_status = 503
    message = "A dependency is currently unavailable."
