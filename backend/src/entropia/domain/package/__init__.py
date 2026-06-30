"""Shared package domain surface (doc 09 §2.5). Re-exports only; no logic here."""

from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.kind import LEGACY_PACKAGE_TYPES, ensure_package_kind

__all__ = [
    "LEGACY_PACKAGE_TYPES",
    "PackageValidationState",
    "ensure_package_kind",
]
