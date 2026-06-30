"""Create-Package request normalization + hashing (docs 06 §4, 07 §4; IR-4..IR-7).

Pure functions over the request inputs:

* ``source_kind_for_mode`` derives ``code``/``description`` from the creation mode.
* ``normalize_request`` validates field requiredness (language required for code,
  forbidden for description; ``other`` needs a label; output contract kind allowed
  for the package type) and returns the normalized tuple.
* ``source_hash`` / ``context_hash`` are the staleness anchors: any change to the
  source body, language, runtime, output contract or declared dependencies yields
  a different ``context_hash``, so a prior Pre-Check result no longer applies
  (doc 07 §4 critical rule, IR-5).

No I/O. The application layer feeds persisted/request values in and stores the
results; the resolver registry is consulted separately by the Pre-Check command.
"""

from __future__ import annotations

from dataclasses import dataclass

from entropia.domain.create_package.enums import (
    CREATE_PACKAGE_KINDS,
    CreationMode,
    SourceKind,
    SourceLanguage,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import PackageKind
from entropia.domain.package.kind import ensure_package_kind
from entropia.domain.revision.hashing import content_hash
from entropia.shared.errors import (
    ClientLegacyTypeRejected,
    EmptySource,
    OutputContractInvalid,
    RuntimeUnavailable,
    SourceLanguageMismatch,
    ValidationError,
)

# Modes whose source is supplied code (vs a natural-language description).
_CODE_MODES: frozenset[CreationMode] = frozenset(
    {
        CreationMode.TRANSLATE_EXISTING_CODE,
        CreationMode.REPAIR_EXISTING_CODE,
        CreationMode.REVIEW_EXISTING_CODE,
    }
)

# Output-contract ``kind`` values allowed per package type (doc 06 §4.3).
_OUTPUT_KINDS_BY_KIND: dict[PackageKind, frozenset[str]] = {
    PackageKind.INDICATOR: frozenset(
        {"directional_signal", "numeric_series", "state_series", "boolean_event"}
    ),
    PackageKind.CONDITION: frozenset({"boolean_condition"}),
    PackageKind.EMBEDDED_SYSTEM: frozenset(
        {"directional_signal", "numeric_series", "state_series", "boolean_event", "resolver_output"}
    ),
}

# V1 fixes the runtime to the registered Python adapter (doc 06 §4.2 Impl.
# Decision, IR-6). PHP/other adapters are Future-Dev.
SUPPORTED_TARGET_RUNTIMES: frozenset[RuntimeAdapter] = frozenset({RuntimeAdapter.PYTHON})


@dataclass(frozen=True, slots=True)
class NormalizedRequest:
    """The validated, normalized create-package request inputs."""

    package_kind: PackageKind
    creation_mode: CreationMode
    source_kind: SourceKind
    source_language: SourceLanguage | None
    other_language_label: str | None
    target_runtime: RuntimeAdapter
    output_contract: dict[str, object]


def source_kind_for_mode(mode: CreationMode) -> SourceKind:
    """Code modes carry code; Generate From Description carries a description."""
    return SourceKind.CODE if mode in _CODE_MODES else SourceKind.DESCRIPTION


def ensure_create_package_kind(value: str | PackageKind) -> PackageKind:
    """Coerce + restrict the package type to the Create-Package subset (CR-01).

    Reuses the shared kind guard (rejects ``trading_signal``/``trade_log``), then
    rejects ``strategy`` — strategy packages are produced by the separate Add
    Package derive path, not Create Package (doc 06 §1.1 Canonical Rule).
    """
    kind = ensure_package_kind(value)
    if kind not in CREATE_PACKAGE_KINDS:
        raise ClientLegacyTypeRejected(
            f"Package type '{kind}' cannot be produced from Create Package."
        )
    return kind


def normalize_request(
    *,
    package_type: str | PackageKind,
    creation_mode: CreationMode,
    source_language: SourceLanguage | None,
    other_language_label: str | None,
    target_runtime: RuntimeAdapter,
    request_body: str,
    output_contract: dict[str, object],
) -> NormalizedRequest:
    """Validate field requiredness and return the normalized request (doc 06 §4).

    Raises typed errors: ``ClientLegacyTypeRejected`` (bad type), ``EmptySource``
    (blank body), ``SourceLanguageMismatch`` (language present/absent against the
    mode, or ``other`` without a label), ``RuntimeUnavailable`` (unsupported
    runtime), ``OutputContractInvalid`` (missing/incompatible output kind).
    """
    kind = ensure_create_package_kind(package_type)
    if not request_body.strip():
        raise EmptySource()
    if target_runtime not in SUPPORTED_TARGET_RUNTIMES:
        raise RuntimeUnavailable(f"Target runtime '{target_runtime}' is not a registered adapter.")

    source_kind = source_kind_for_mode(creation_mode)
    normalized_language, normalized_label = _normalize_language(
        source_kind, source_language, other_language_label
    )
    _validate_output_contract(kind, output_contract)
    return NormalizedRequest(
        package_kind=kind,
        creation_mode=creation_mode,
        source_kind=source_kind,
        source_language=normalized_language,
        other_language_label=normalized_label,
        target_runtime=target_runtime,
        output_contract=output_contract,
    )


def _normalize_language(
    source_kind: SourceKind,
    source_language: SourceLanguage | None,
    other_language_label: str | None,
) -> tuple[SourceLanguage | None, str | None]:
    if source_kind == SourceKind.DESCRIPTION:
        # Description requests never carry a code-language parser (IR-7).
        return None, None
    if source_language is None:
        raise SourceLanguageMismatch("A source language is required for a code request.")
    if source_language == SourceLanguage.OTHER:
        label = (other_language_label or "").strip()
        if not label:
            raise SourceLanguageMismatch(
                "Enter the exact language and version for 'Other' before continuing."
            )
        return source_language, label
    return source_language, None


def _validate_output_contract(kind: PackageKind, output_contract: dict[str, object]) -> None:
    raw_kind = output_contract.get("kind") or output_contract.get("output_type")
    if not raw_kind or not isinstance(raw_kind, str):
        raise OutputContractInvalid("An output contract kind is required.")
    allowed = _OUTPUT_KINDS_BY_KIND.get(kind, frozenset())
    if raw_kind not in allowed:
        raise OutputContractInvalid(
            f"Output kind '{raw_kind}' is not valid for a '{kind}' package."
        )


def source_hash(request_body: str) -> str:
    """Normalized hash of the source body — the per-source staleness anchor."""
    return f"sha256:{content_hash({'source': request_body})}"


def context_hash(
    *,
    source_hash_value: str,
    source_language: SourceLanguage | None,
    target_runtime: RuntimeAdapter,
    output_contract: dict[str, object],
    declared_dependencies: list[dict[str, object]] | None,
) -> str:
    """Hash every input that invalidates a prior Pre-Check (doc 07 §4, IR-5).

    Any change to the source, language, runtime, output contract or the declared
    dependency set produces a different value, so a Passed/Blocked scan pinned to
    the old ``context_hash`` is treated as stale.
    """
    payload = {
        "source_hash": source_hash_value,
        "source_language": str(source_language) if source_language else None,
        "target_runtime": str(target_runtime),
        "output_contract": output_contract,
        "declared_dependencies": declared_dependencies or [],
    }
    return f"sha256:{content_hash(payload)}"


def clean_declared_dependencies(
    raw: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    """Validate the optional declared-dependency list (the V1 Pre-Check input).

    Each entry must carry a non-empty ``key`` (canonical resolver key) and may
    carry a ``signature`` dict. A real PineScript parser replaces this declared
    list in a later stage; until then the request explicitly states the canonical
    TA calls so Pre-Check can resolve them against the trusted ESP registry.
    """
    if raw is None:
        return []
    cleaned: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in raw:
        key = str(entry.get("key", "")).strip()
        if not key:
            raise ValidationError("Each declared dependency requires a canonical 'key'.")
        if key in seen:
            raise ValidationError(f"Duplicate declared dependency '{key}'.")
        seen.add(key)
        signature = entry.get("signature")
        cleaned.append({"key": key, "signature": signature if isinstance(signature, dict) else {}})
    return cleaned
