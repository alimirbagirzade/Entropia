"""Create Package + Pre-Check domain (docs 06, 07; Stage 2e)."""

from __future__ import annotations

from entropia.domain.create_package.baseline import (
    BASELINE_PARSER_VERSION,
    REQUIRED_BASELINE_METADATA_FIELDS,
    BaselineParseReport,
    is_allowed_baseline_file,
    missing_baseline_metadata_fields,
    parse_baseline_csv,
    resolve_equivalence_claim,
)
from entropia.domain.create_package.enums import (
    CREATE_PACKAGE_KINDS,
    BaselineParseStatus,
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
    ValidationRunStatus,
)
from entropia.domain.create_package.policy import (
    ensure_can_approve_publish,
    ensure_can_create_request,
    ensure_can_operate_request,
)
from entropia.domain.create_package.source_scan import (
    SCANNED_NAMESPACES,
    SOURCE_SCANNER_VERSION,
    SourceScanResult,
    is_scannable_key,
    scan_source_calls,
)
from entropia.domain.create_package.state_machine import (
    SCAN_BLOCKING_STATES,
    next_request_state,
    next_scan_status,
)
from entropia.domain.create_package.validation import (
    VALIDATOR_VERSION,
    DependencyResolution,
    ValidationReport,
    build_validation_report,
)
from entropia.domain.create_package.value_objects import (
    SUPPORTED_TARGET_RUNTIMES,
    NormalizedRequest,
    clean_declared_dependencies,
    context_hash,
    ensure_create_package_kind,
    normalize_request,
    source_hash,
    source_kind_for_mode,
)

__all__ = [
    "BASELINE_PARSER_VERSION",
    "CREATE_PACKAGE_KINDS",
    "REQUIRED_BASELINE_METADATA_FIELDS",
    "SCANNED_NAMESPACES",
    "SCAN_BLOCKING_STATES",
    "SOURCE_SCANNER_VERSION",
    "SUPPORTED_TARGET_RUNTIMES",
    "VALIDATOR_VERSION",
    "BaselineParseReport",
    "BaselineParseStatus",
    "CreatePackageState",
    "CreationMode",
    "DependencyResolution",
    "NormalizedRequest",
    "PrecheckScanStatus",
    "SourceKind",
    "SourceLanguage",
    "SourceScanResult",
    "ValidationReport",
    "ValidationRunStatus",
    "build_validation_report",
    "clean_declared_dependencies",
    "context_hash",
    "ensure_can_approve_publish",
    "ensure_can_create_request",
    "ensure_can_operate_request",
    "ensure_create_package_kind",
    "is_allowed_baseline_file",
    "is_scannable_key",
    "missing_baseline_metadata_fields",
    "next_request_state",
    "next_scan_status",
    "normalize_request",
    "parse_baseline_csv",
    "resolve_equivalence_claim",
    "scan_source_calls",
    "source_hash",
    "source_kind_for_mode",
]
