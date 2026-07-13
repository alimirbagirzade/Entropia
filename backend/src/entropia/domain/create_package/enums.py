"""Create Package + Pre-Check per-domain enums (docs 06, 07; DOMAIN_MODEL §3.2).

All values are lowercase snake_case and are returned over REST/SSE verbatim
(CR-04). The create-package flow state, the Pre-Check scan status, the creation
mode and the source kind/language are SEPARATE facets — none collapse into a
single column and none alias the shared package validation/approval/visibility
enums.
"""

from __future__ import annotations

from enum import StrEnum

from entropia.domain.lifecycle.enums import PackageKind

# Package kinds a Create Package request may target. Strategy is produced by the
# separate Strategy domain (Add Package derive path); trading_signal / trade_log
# are external Mainboard working objects and are rejected with the typed
# ClientLegacyTypeRejected error by ``ensure_create_package_kind`` (CR-01).
CREATE_PACKAGE_KINDS: frozenset[PackageKind] = frozenset(
    {PackageKind.INDICATOR, PackageKind.CONDITION, PackageKind.EMBEDDED_SYSTEM}
)


class CreationMode(StrEnum):
    """How a candidate is produced from the request (doc 06 §4.2).

    Translate/Repair/Review require ``source_kind=code``; Generate requires
    ``source_kind=description``. Review alone never publishes a package.
    """

    TRANSLATE_EXISTING_CODE = "translate_existing_code"
    GENERATE_FROM_DESCRIPTION = "generate_from_description"
    REPAIR_EXISTING_CODE = "repair_existing_code"
    REVIEW_EXISTING_CODE = "review_existing_code"


class SourceKind(StrEnum):
    """Normalized source kind derived server-side from the creation mode (doc 06
    §4.2, IR-4/IR-7). Description requests carry ``source_language=null`` and skip
    the Pre-Check dependency gate (NOT_APPLICABLE)."""

    CODE = "code"
    DESCRIPTION = "description"


class SourceLanguage(StrEnum):
    """Supplied-code language (doc 06 §4.2). Required only for ``source_kind=code``.

    Natural Language is NOT a source language — it maps to Generate From
    Description with ``source_language=null`` (doc 06 §4.2, §14.4). ``other``
    requires an ``other_language_label``.
    """

    PINESCRIPT = "pinescript"
    PYTHON = "python"
    CPP = "cpp"
    OTHER = "other"


class CreatePackageState(StrEnum):
    """End-to-end Create-Package flow state (DOMAIN_MODEL §3.2).

    A read-only workflow projection, never inferred from a UI button click. The
    transitions and guards are validated by ``state_machine.next_request_state``.
    """

    REQUESTED = "requested"
    PRECHECK_PASSED = "precheck_passed"
    PRECHECK_BLOCKED = "precheck_blocked"
    PRECHECK_NOT_APPLICABLE = "precheck_not_applicable"
    PRECHECK_STALE = "precheck_stale"
    PRECHECK_FAILED = "precheck_failed"
    CANDIDATE_GENERATING = "candidate_generating"
    CANDIDATE_READY = "candidate_ready"
    CANDIDATE_FAILED = "candidate_failed"
    DRAFT_CREATED = "draft_created"
    VALIDATION_RUNNING = "validation_running"
    EXPERIMENTAL = "experimental"
    ELIGIBLE_FOR_APPROVAL = "eligible_for_approval"
    REVISION_REQUIRED = "revision_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class PrecheckScanStatus(StrEnum):
    """Immutable Pre-Check dependency-scan result (DOMAIN_MODEL §3.2, doc 07 §4).

    ``checking`` is the transient in-flight state; the terminal results drive the
    request projection. ``passed``/``blocked`` become ``stale`` (computed on read)
    when the source/runtime/output context or the resolver registry changes.
    """

    NOT_CHECKED = "not_checked"
    CHECKING = "checking"
    PASSED = "passed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"
    STALE = "stale"


class ValidationRunStatus(StrEnum):
    """Immutable package validation-run result (doc 06 §4.4/§5/§7).

    ``queued``/``running`` are transient; the terminal results drive the request
    projection and the approval gate. A ``passed`` run becomes ``stale`` (computed
    on read) when the draft candidate it validated is regenerated — evidence is
    never a cosmetic label, it pins the exact candidate it certified.
    """

    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    STALE = "stale"


class BaselineParseStatus(StrEnum):
    """Immutable baseline-asset parse result (doc 06 §4.4/§5/§8.3).

    ``uploaded`` is the freshly-stored state before the parse runs; ``parsing`` is
    the transient in-flight state. A ``passed`` parse is the equivalence-comparison
    evidence the mode-aware approval baseline gate reads. A file upload alone is
    never proof of equivalence — the parse must confirm the CSV and its metadata.
    """

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PASSED = "passed"
    FAILED = "failed"
