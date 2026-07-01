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


class AdminPanelAccessRequiredError(ForbiddenError):
    """Panel / Management / Logs is Admin-only (doc 19 §2). UI hide/disable is
    never a substitute for this server-side guard."""

    code = "ADMIN_PANEL_ACCESS_REQUIRED"
    message = "Admin access is required to use Panel."


class UserRoleVersionConflictError(ConflictError):
    """A role assignment supplied a stale ``expected_head_revision_id`` / ``If-Match``
    (doc 19 §9.2, §11). No last-write-wins overwrite is applied; reload and retry."""

    code = "USER_ROLE_VERSION_CONFLICT"
    message = "This user record was updated by another Admin. The latest values have been loaded."


class LogFilterInvalidError(ValidationError):
    """A Logs query supplied an unknown/deprecated filter value (doc 19 §6.2).
    The server rejects it rather than silently returning an unfiltered page."""

    code = "LOG_FILTER_INVALID"
    message = "One or more log filters are invalid."


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


class CatalogFilterInvalid(ValidationError):
    """A Package Library catalog filter value was not a valid facet (doc 08 §5).

    The catalog never silently substitutes another value — an invalid
    lifecycle/validation/approval/visibility facet is rejected so the client can
    correct it (an invalid/legacy *type* is rejected by ``ClientLegacyTypeRejected``
    via the canonical package-kind guard, CR-01).
    """

    code = "CATALOG_FILTER_INVALID"
    message = "One or more catalog filters are not valid."


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


# --- Stage 3a — Mainboard composition plane (doc 01; ARCHITECTURE §9.2) ---


class MainboardItemKindMismatchError(ValidationError):
    """CR-01 kind guard: a working item's kind diverged from its root's object
    kind (doc 01; DOMAIN_MODEL §2.2). Item kind is server-derived from the root;
    a client-supplied kind that disagrees is rejected, never coerced."""

    code = "MAINBOARD_ITEM_KIND_MISMATCH"
    message = "The item kind does not match the work object's kind."


class ObjectNotActiveError(ConflictError):
    """A work object referenced by an attach/pin/revision is not ACTIVE
    (soft-deleted or otherwise not live). Operations require a live root."""

    code = "OBJECT_NOT_ACTIVE"
    message = "The work object is not active."


class ObjectInActiveRunError(ConflictError):
    """A work object cannot be soft-deleted because a queued/running backtest
    references it (Stage 5). The 3a preflight is a no-op stub; reserved here."""

    code = "OBJECT_IN_ACTIVE_RUN"
    message = "This work object is in use by an active run and cannot be deleted."


class RowVersionConflictError(ConflictError):
    """A working-item mutation supplied a stale ``expected_row_version`` (doc 01
    §9.4). No last-write-wins overwrite is applied."""

    code = "ROW_VERSION_CONFLICT"
    message = "This item changed after you loaded it. Reload the current version and retry."


class WorkObjectRevisionConflictError(ConflictError):
    """A work-object revision append supplied a stale ``expected_head_revision_id``
    (doc 01 §9.4). The head advanced; reload and retry."""

    code = "WORK_OBJECT_REVISION_CONFLICT"
    message = "This work object's head changed. Reload the current revision and retry."


class WorkObjectNotFoundError(NotFoundError):
    """A referenced work object root did not resolve as an active work object."""

    code = "WORK_OBJECT_NOT_FOUND"
    message = "The work object was not found."


class MainboardWorkspaceNotFoundError(NotFoundError):
    """A referenced Mainboard workspace did not resolve as an active workspace."""

    code = "MAINBOARD_WORKSPACE_NOT_FOUND"
    message = "The Mainboard workspace was not found."


class MainboardItemNotFoundError(NotFoundError):
    """A referenced Mainboard working item did not resolve."""

    code = "MAINBOARD_ITEM_NOT_FOUND"
    message = "The Mainboard item was not found."


# --- Stage 3b — Strategy Details (doc 02; DOMAIN_MODEL §2.3) ---


class StrategyNotFoundError(NotFoundError):
    """A referenced strategy root did not resolve as an active strategy."""

    code = "STRATEGY_NOT_FOUND"
    message = "The strategy was not found."


class StrategyDraftNotFoundError(NotFoundError):
    """A referenced strategy editor draft did not resolve."""

    code = "STRATEGY_DRAFT_NOT_FOUND"
    message = "The strategy draft was not found."


class StrategyRevisionNotFoundError(NotFoundError):
    """A referenced immutable strategy revision did not resolve."""

    code = "STRATEGY_REVISION_NOT_FOUND"
    message = "The strategy revision was not found."


class StrategyDraftConflictError(ConflictError):
    """A draft mutation supplied a stale ``expected_draft_row_version`` (doc 02
    §7, §8.2). No last-write-wins overwrite is applied; the caller reloads the
    current draft (changed paths) and chooses Reload / Merge / Fork / Discard."""

    code = "STRATEGY_DRAFT_CONFLICT"
    message = "This draft changed in another session. Reload the latest version before saving."


class StrategyDraftNotAttachedError(ValidationError):
    """A Save was attempted on a transient draft with no strategy root. A draft
    must be bound to a root (created via POST /strategy-drafts) before Save."""

    code = "STRATEGY_DRAFT_NOT_ATTACHED"
    message = "This draft is not attached to a strategy root and cannot be saved."


class StrategyValidationFailedError(ValidationError):
    """The StrategyConfig failed semantic validation; no immutable revision is
    produced (doc 02 §7.1). The issue envelope carries machine codes + paths."""

    code = "STRATEGY_VALIDATION_FAILED"
    message = "The strategy configuration has validation errors and cannot be saved."


class SizingMethodNotExclusiveError(ValidationError):
    """More than one Position Sizing method was active (doc 02 §6, AT-12).
    Exactly one method must be selected."""

    code = "SIZING_METHOD_NOT_EXCLUSIVE"
    message = "Select exactly one Position Sizing method."


class TriggerSourceConditionRequiredError(ValidationError):
    """A condition-bearing Trigger Source (Native+Condition / Output+Condition)
    has no compatible active Condition block (doc 02 §3, AT-05)."""

    code = "TRIGGER_SOURCE_CONDITION_REQUIRED"
    message = "Add at least one compatible Condition for the selected Trigger Source."


class StrategyLockedForTestError(ConflictError):
    """The strategy root is locked_for_test and cannot be edited in place;
    clone-to-draft is required (doc 02 §7, DOMAIN_MODEL §3.2)."""

    code = "STRATEGY_LOCKED_FOR_TEST"
    message = "This strategy is locked for testing. Clone it to a new draft to continue editing."


class StrategyReferenceNotActiveError(ConflictError):
    """A pinned dependency (package/dataset) is no longer active at Save time
    (doc 02 §8.2). Historical revisions/runs are unchanged; reselect an active
    revision or have an Admin restore it."""

    code = "REFERENCE_NOT_ACTIVE"
    message = "A referenced dependency is no longer active. Select another revision."


# --- Stage 3c — Trading Signal / Add Outsource Signal (docs 03, 04) ---


class SourceProviderRequiredError(ValidationError):
    """A Trading Signal Save had a blank source/provider (doc 04 §5, §8.3, TS-03)."""

    code = "SOURCE_PROVIDER_REQUIRED"
    message = "Enter the source or provider for this Trading Signal."


class TradingSignalValidationFailedError(ValidationError):
    """The Trading Signal §9.2 payload failed structural/cross-field validation
    (doc 04 §7.1, §11). The issue envelope carries machine codes + field paths;
    no immutable revision is produced."""

    code = "TRADING_SIGNAL_VALIDATION_FAILED"
    message = "The Trading Signal configuration has validation errors and cannot be saved."


class EventModelPolicyConflictError(ValidationError):
    """Event model conflicts with the timeframe selection (doc 04 §5.2, §11).
    e.g. an event-based source carrying a fixed base timeframe."""

    code = "EVENT_MODEL_POLICY_CONFLICT"
    message = "The event model conflicts with the selected base timeframe."


class OhlcvPolicyConflictError(ValidationError):
    """Price/OHLCV policy is internally inconsistent (doc 04 §5.2, §11, TS-09).
    e.g. Ignore OHLCV combined with an intrabar price policy."""

    code = "OHLCV_POLICY_CONFLICT"
    message = "The OHLCV and price policy selections are incompatible."


class FileTypeNotAllowedError(ValidationError):
    """An uploaded source asset was not an accepted TXT/CSV file (doc 04 §11)."""

    code = "FILE_TYPE_NOT_ALLOWED"
    message = "Upload a TXT or CSV signal-event file."


class SourceAssetNotFoundError(NotFoundError):
    """A referenced raw source asset did not resolve (doc 04 §7.1, §11)."""

    code = "SOURCE_ASSET_NOT_FOUND"
    message = "The source asset was not found."


class ImportJobNotFoundError(NotFoundError):
    """A referenced Trading Signal import job did not resolve (doc 04 §7)."""

    code = "IMPORT_JOB_NOT_FOUND"
    message = "The import job was not found."


class NormalizedRevisionNotFoundError(NotFoundError):
    """A referenced normalized signal-event revision did not resolve (doc 04 §7.1)."""

    code = "NORMALIZED_REVISION_NOT_FOUND"
    message = "The normalized import revision was not found."


class AvailableTimeRequiredError(ValidationError):
    """The normalized import lacks a valid per-event ``available_time`` (doc 04 §5.1,
    §11, TS-05). Availability is never inferred from render/import time; a new
    import revision with a valid availability rule is required."""

    code = "AVAILABLE_TIME_REQUIRED"
    message = "Every accepted signal event needs a valid available time before Save."


class SignalEventMappingRequiredError(ValidationError):
    """The source file does not resolve the canonical signal-event contract
    (doc 04 §5.1, §11, TS-06). A legacy entry/exit ledger is not silently accepted
    as a Trading Signal; explicit event mapping or the Trade Log flow is required."""

    code = "SIGNAL_EVENT_MAPPING_REQUIRED"
    message = (
        "Map event_time, available_time, source_record_id and signal_type, "
        "or import as a Trade Log."
    )


class NoAcceptedSignalEventsError(ValidationError):
    """The import produced zero accepted events (doc 04 §11, TS-05). Save/attach
    cannot proceed on an empty normalized revision."""

    code = "NO_ACCEPTED_SIGNAL_EVENTS"
    message = "No accepted signal events are available. Fix the source file or mapping."


class ImportNotReadyError(ConflictError):
    """A Save referenced a normalized import revision that has not succeeded
    (doc 04 §11, TS: import durability). Wait for the durable import to finish."""

    code = "IMPORT_NOT_READY"
    message = "The signal import has not finished successfully yet."


# --- Stage 3d — Trade Log (doc 05) ---


class TradeLogValidationFailedError(ValidationError):
    """The Trade Log §10.2 payload failed structural/cross-field validation
    (doc 05 §10.5, §12). The issue envelope carries machine codes + field paths;
    no immutable revision is produced (TL-03)."""

    code = "TRADE_LOG_VALIDATION_FAILED"
    message = "The Trade Log configuration has validation errors and cannot be saved."


class TradeLogPriceContextConflictError(ValidationError):
    """Price Source / OHLCV Use / Data Quality selections are internally inconsistent
    (doc 05 §5.2, §12, TL-10). e.g. an OHLCV price fallback combined with
    Ignore OHLCV context."""

    code = "PRICE_CONTEXT_CONFLICT"
    message = "The OHLCV and price policy selections are incompatible."


class SourceFileRequiredError(ValidationError):
    """Validate & Save Ready was attempted without a source-file import binding
    (doc 05 §5.2, §12, TL-04). Save Draft may omit the file; a Ready revision may not."""

    code = "SOURCE_FILE_REQUIRED"
    message = "Select a TXT or CSV source file before validating this Trade Log revision."


class RequiredColumnMissingError(ValidationError):
    """The source file omits a canonical required column (doc 05 §5.4, §12, TL-05).
    Required: direction, entry_time, entry_price, exit_time, exit_price."""

    code = "REQUIRED_COLUMN_MISSING"
    message = "The file must provide direction, entry_time, entry_price, exit_time and exit_price."


class TradeRecordBatchNotFoundError(NotFoundError):
    """A referenced canonical trade-record batch did not resolve (doc 05 §10.5)."""

    code = "TRADE_RECORD_BATCH_NOT_FOUND"
    message = "The trade-record batch was not found."


class NoAcceptedTradeRecordsError(ValidationError):
    """The import produced zero accepted records (doc 05 §12, TL-05). Save/attach
    cannot proceed on an empty record batch."""

    code = "NO_ACCEPTED_TRADE_RECORDS"
    message = "No accepted trade records are available. Fix the source file or mapping."


# --------------------------------------------------------------------------- #
# Stage 4a — Portfolio / Equity Allocation (doc 13 §10)                        #
# --------------------------------------------------------------------------- #


class CompositionNotFoundError(NotFoundError):
    """The target Mainboard composition (workspace) is missing or inaccessible."""

    code = "COMPOSITION_NOT_FOUND"
    message = "The mainboard composition was not found or is not accessible."


class AllocationPlanNotFoundError(NotFoundError):
    """No allocation plan has been created for this composition yet (doc 13 §7)."""

    code = "ALLOCATION_PLAN_NOT_FOUND"
    message = "No portfolio allocation plan exists for this composition yet."


class AllocationDraftConflictError(ConflictError):
    """Stale ``expected_row_version`` on an allocation draft (doc 13 §7.2, §10.1)."""

    code = "ALLOCATION_DRAFT_CONFLICT"
    message = "This allocation draft changed elsewhere. Refresh, compare, then reapply your update."


class AllocationValidationFailedError(ValidationError):
    """The allocation config failed structural/field validation (doc 13 §10.1)."""

    code = "ALLOCATION_VALIDATION_FAILED"
    message = "The allocation configuration failed validation."


class AllocationDependencyBlockedError(ValidationError):
    """An entry references an item that is not a current, accessible composition
    member (doc 13 §14#7)."""

    code = "DEPENDENCY_BLOCKED"
    message = (
        "An allocation entry references an item that is not a current, accessible "
        "composition member."
    )


class AllocationHasBlockersError(ValidationError):
    """A plan revision was requested from a draft that still has blocking issues
    (doc 13 §7, §10.1)."""

    code = "ALLOCATION_HAS_BLOCKERS"
    message = "The allocation configuration has blocking issues and cannot become a plan revision."


class CompositionStaleError(ConflictError):
    """The composition changed since the caller's ``expected_fingerprint`` (doc 14
    §11, RC-09). No snapshot/report/run is created."""

    code = "COMPOSITION_STALE"
    message = "The composition changed since this check was requested. Re-run the Ready Check."


class ReadinessReportNotFoundError(NotFoundError):
    """The requested readiness report does not exist or is not accessible (doc 14 §9.1)."""

    code = "READINESS_REPORT_NOT_FOUND"
    message = "The readiness report was not found or is not accessible."


# --------------------------------------------------------------------------- #
# Stage 5a — RUN + Backtest Results (doc 15 §7, §11)                           #
# --------------------------------------------------------------------------- #


class ReadinessBlockedError(ValidationError):
    """RUN admission re-ran the mandatory server preflight and it produced a
    blocker (doc 15 §11, §15). No snapshot/manifest/run/job is created; the client
    ``ready`` flag is never trusted. The blocking issues ride in ``details``."""

    code = "READINESS_BLOCKED"
    message = "The composition is not ready to run. Resolve the blocking issues and re-check."


class ReadyReportStaleError(ConflictError):
    """A supplied ``ready_report_id`` is not valid for the current composition
    fingerprint (doc 15 §11 READY_REPORT_STALE). The old report may be shown but
    RUN admission is refused; a fresh Ready Check is required."""

    code = "READY_REPORT_STALE"
    message = "Readiness was checked against an older composition. Re-run the Ready Check."


class BacktestRunNotFoundError(NotFoundError):
    """A referenced Backtest Run did not resolve or is not accessible (doc 15 §7)."""

    code = "BACKTEST_RUN_NOT_FOUND"
    message = "The backtest run was not found."


class BacktestResultNotFoundError(NotFoundError):
    """A referenced Backtest Result did not resolve, is soft-deleted, or is not
    accessible (doc 15 §7)."""

    code = "BACKTEST_RESULT_NOT_FOUND"
    message = "The backtest result was not found."


class RunNotRetryableError(ConflictError):
    """Retry was requested on a run that is not a terminal FAILED/CANCELLED run
    (doc 15 §7, §8.4). A succeeded or still-active run is never reset."""

    code = "RUN_NOT_RETRYABLE"
    message = "Only a failed or cancelled run can be retried."


# --------------------------------------------------------------------------- #
# Stage 5b — Results History (doc 16 §5, §12)                                  #
# --------------------------------------------------------------------------- #


class InvalidSortKeyError(ValidationError):
    """An unknown/unsupported Results History sort enum was requested (doc 16 §5,
    §12). The client never silently falls back to a known enum; it re-queries with
    the default ``newest_current`` after showing the error."""

    code = "INVALID_SORT_KEY"
    message = "That sort option is not supported."


class CursorInvalidError(ValidationError):
    """A history cursor was expired, malformed, or built for a different query
    fingerprint (doc 16 §5, §12). The appended local list is discarded and the
    first page is refetched; partial/duplicated data is never appended."""

    code = "CURSOR_INVALID"
    message = "This results page cursor is no longer valid. Reload the first page."


class CompareRequiresTwoDistinctResultsError(ValidationError):
    """Result comparison requires exactly two DISTINCT visible results (doc 16 §5,
    §8.3, RH-10). Same id twice or a count other than two is rejected; results are
    never mutated."""

    code = "COMPARE_REQUIRES_TWO_DISTINCT_RESULTS"
    message = "Select exactly two different results to compare."


# --------------------------------------------------------------------------- #
# Stage 5c — Arrange Metrics (doc 17 §11) + doc-15 deferred (export + artifacts) #
# --------------------------------------------------------------------------- #


class MetricProfileNotFoundError(NotFoundError):
    """A referenced Result View Metric Profile root did not resolve (doc 17 §7)."""

    code = "METRIC_PROFILE_NOT_FOUND"
    message = "The metric profile was not found."


class MetricSelectionEmptyError(ValidationError):
    """An Apply payload carried no SELECTABLE metric (doc 17 §5, §11, AT-05). The
    minimum-one-selectable rule keeps a Result Summary from becoming empty; the
    current canonical profile is preserved and no revision is created."""

    code = "METRIC_SELECTION_EMPTY"
    message = "Select at least one available metric before applying this profile."


class MetricCodeUnknownError(ValidationError):
    """A selected ``metric_code`` is absent from the registry (doc 17 §11)."""

    code = "METRIC_CODE_UNKNOWN"
    message = (
        "One or more selected metrics are no longer recognized by the metric "
        "registry. Reload the page and choose available metrics."
    )


class MetricNotSelectableError(ValidationError):
    """A known but future/experimental code was submitted for Apply (doc 17 §11,
    §14, AT-04). A future metric is reference-only and never enters a revision."""

    code = "METRIC_NOT_SELECTABLE"
    message = "That metric is not selectable in the current metric registry and cannot be applied."


class MetricProfileLockedError(ConflictError):
    """An Apply changed a selection while the current revision is locked (doc 17
    §11 METRIC_PROFILE_LOCKED). Unlock first; lock is a preference, not a grant."""

    code = "METRIC_PROFILE_LOCKED"
    message = "Metrics are locked. Unlock this profile before changing the selection."


class MetricProfileStaleError(ConflictError):
    """``expected_profile_revision_id`` did not match the current head (doc 17 §11
    METRIC_PROFILE_STALE, §8.5). No silent overwrite; reload the latest revision."""

    code = "METRIC_PROFILE_STALE"
    message = (
        "Metric profile changed elsewhere. Reload the latest profile before saving your changes."
    )


class ExportTypeInvalidError(ValidationError):
    """An unknown Result export type was requested (doc 15 §7, §11)."""

    code = "EXPORT_TYPE_INVALID"
    message = "That export type is not supported for this result."


class ExportFormatInvalidError(ValidationError):
    """An unknown Result export format was requested (doc 15 §7, §11)."""

    code = "EXPORT_FORMAT_INVALID"
    message = "That export format is not supported."


class ArtifactTypeInvalidError(ValidationError):
    """An unknown Result artifact drill-down type was requested (doc 15 §7)."""

    code = "ARTIFACT_TYPE_INVALID"
    message = "That result artifact type is not available."


class ArtifactNotAvailableError(NotFoundError):
    """The requested artifact scope produced no rows / is not retained (doc 15 §7
    ARTIFACT_NOT_AVAILABLE). A soft-deleted or missing result is BACKTEST_RESULT_NOT_FOUND."""

    code = "ARTIFACT_NOT_AVAILABLE"
    message = "This result artifact is not available."


# --- Analysis Lab (Stage 6a, doc 18) ----------------------------------------


class MessageTextRequiredError(ValidationError):
    """A blank/whitespace discussion message or directive text was submitted
    (doc 18 §6.1, §11 AL-06)."""

    code = "MESSAGE_TEXT_REQUIRED"
    message = "Enter a message before sending."


class InvalidDirectivePriorityError(ValidationError):
    """A directive priority outside the human-selectable set (``normal | high``)
    was submitted — e.g. ``autonomous`` or an unknown value (doc 18 §11 AL-07)."""

    code = "INVALID_DIRECTIVE_PRIORITY"
    message = "Directive priority must be normal or high."


class DirectiveTargetInvalidError(ValidationError):
    """The directive target agent is unknown or not eligible (doc 18 §5, §7)."""

    code = "DIRECTIVE_TARGET_INVALID"
    message = "The directive target agent is not available."


class AgentRuntimeNotFoundError(NotFoundError):
    """The Alpha Agent runtime record was not found (doc 18 §9)."""

    code = "AGENT_RUNTIME_NOT_FOUND"
    message = "The Agent runtime is not available."


class AgentTaskNotFoundError(NotFoundError):
    """The requested Agent task was not found or is not viewable (doc 18 §7, §9)."""

    code = "AGENT_TASK_NOT_FOUND"
    message = "The Agent task was not found."


class HypothesisArtifactNotFoundError(NotFoundError):
    """The requested hypothesis/output artifact was not found (doc 18 §7, §9)."""

    code = "HYPOTHESIS_NOT_FOUND"
    message = "The hypothesis artifact was not found."


class AgentRuntimeStateConflictError(StaleRevisionError):
    """A runtime lifecycle command raced another (stale expected version / a
    control already pending) — doc 18 §11 AL-17."""

    code = "AGENT_RUNTIME_STATE_CONFLICT"
    message = (
        "Analysis Lab state changed elsewhere. Reload the latest runtime state "
        "before sending another control command."
    )


class AgentRunNotStoppableError(ConflictError):
    """Stop Current Run was requested with no active, stoppable Agent sub-run
    (doc 18 §4, §7)."""

    code = "AGENT_RUN_NOT_STOPPABLE"
    message = "There is no active run to stop."


class ToolPolicyScopeError(ForbiddenError):
    """An agent tool call was made under a scope the tool does not allow, or the
    tool/scope name is unknown (doc 18 §9.2, §10). Recorded as a REJECTED tool
    call, never a silent crash."""

    code = "AGENT_TOOL_SCOPE_FORBIDDEN"
    message = "This tool cannot run under the requested policy scope."


class ResearchInputBlockedError(ForbiddenError):
    """An ``agent_research_only`` revision was routed into an execution / backtest
    context (doc 18 §9.1, §14, AL-11). The invalid bundle never enters a run
    manifest; the Gateway records a ``research_input_blocked`` rejection."""

    code = "RESEARCH_INPUT_BLOCKED"
    message = "Agent-research-only data cannot enter an execution or backtest context."


class AgentToolCallForbiddenError(ForbiddenError):
    """The Agent attempted a privileged action it never holds — approve/publish,
    dataset approval, Trash, or human role management (doc 18 §10, §14, AL-12)."""

    code = "AGENT_TOOL_FORBIDDEN"
    message = "The Agent is not permitted to perform this action."


class ArtifactOwnershipError(ForbiddenError):
    """The Agent tried to soft-delete an artifact it does not own; restore /
    permanent delete are Admin-only (doc 18 §12, AL-16)."""

    code = "ARTIFACT_NOT_OWNED"
    message = "The Agent may only soft-delete its own artifacts."
