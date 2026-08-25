"""Deterministic Create-Package candidate generation (doc 06 §5).

Replaces the V1 stub *compute* only. The request lifecycle, Pre-Check resolver,
PC-13 gate, durable job row and dependency-snapshot pinning are already real; this
module composes a reproducible **candidate manifest** from the request's resolved ESP
dependencies and validated output contract, and derives the candidate hash from it.

Reproducibility (INF-04/INF-05): the SAME inputs always yield the SAME manifest and
hash, and bumping ``GENERATOR_VERSION`` shifts the hash namespace so a candidate made
by an older generator is never silently reused. A real LLM/code generator is Future-Dev.

No I/O. The application command feeds resolved refs + output contract in and persists
the resulting ``candidate_hash`` + validated output contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from entropia.domain.create_package.enums import SourceKind
from entropia.domain.revision.hashing import content_hash
from entropia.shared.errors import OutputContractInvalid

# Bumping this shifts the candidate_hash namespace (mirrors ENGINE_VERSION): a manifest
# from an older generator will not collide with a newer one for the same request. v2
# accompanies F-14, where the manifest now underpins a real loadable implementation
# (``domain/create_package/generator``), not a hash-only stub.
GENERATOR_VERSION = "cp-candidate-gen-v2"

# Canonical-key prefixes — used to check the output contract against the resolved deps
# WITHOUT importing the backtest indicator taxonomy (keeps the CP domain independent).
_INDICATOR_KEY_PREFIX = "ta."
_CONDITION_KEY_PREFIX = "cond."

# Output kinds that require a resolved dependency of a given category — enforced ONLY
# when the request actually resolved dependencies. A description or dep-less request
# carries an empty resolved set (implementation deferred) and never fails here.
_KINDS_REQUIRING_INDICATOR: frozenset[str] = frozenset({"directional_signal"})
_KINDS_REQUIRING_CONDITION: frozenset[str] = frozenset({"boolean_condition"})


@dataclass(frozen=True, slots=True)
class CandidateManifest:
    """The deterministic candidate produced from a request's resolved dependencies."""

    generator_version: str
    package_kind: str
    source_kind: str
    signal_kind: str
    output_contract: dict[str, Any]
    resolved_dependencies: list[dict[str, Any]]
    test_plan: list[str]
    uncertainty: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_candidate_manifest(
    *,
    package_kind: str,
    source_kind: SourceKind,
    output_contract: dict[str, Any],
    resolved_refs: list[dict[str, Any]] | None,
) -> CandidateManifest:
    """Compose a deterministic candidate manifest (doc 06 §5).

    Raises ``OutputContractInvalid`` if the output contract has no kind, or if a
    resolved dependency set is present but incompatible with the declared output
    kind (e.g. a ``directional_signal`` with no indicator dependency).
    """
    signal_kind = _output_kind(output_contract)
    resolved = _summarize_resolved(resolved_refs)
    _validate_contract_against_deps(signal_kind, resolved)
    return CandidateManifest(
        generator_version=GENERATOR_VERSION,
        package_kind=package_kind,
        source_kind=str(source_kind),
        signal_kind=signal_kind,
        output_contract=output_contract,
        resolved_dependencies=resolved,
        test_plan=_test_plan(signal_kind, resolved),
        uncertainty=_uncertainty(source_kind, resolved),
    )


def candidate_hash(manifest: CandidateManifest) -> str:
    """The reproducible content hash of the candidate manifest."""
    return f"sha256:{content_hash(manifest.as_dict())}"


def _output_kind(output_contract: dict[str, Any]) -> str:
    raw = output_contract.get("kind") or output_contract.get("output_type")
    if not isinstance(raw, str) or not raw:
        raise OutputContractInvalid("An output contract kind is required to generate a candidate.")
    return raw


def _summarize_resolved(
    resolved_refs: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Order the resolved refs by canonical key so the hash is order-independent."""
    if not resolved_refs:
        return []
    return sorted(
        (dict(ref) for ref in resolved_refs),
        key=lambda ref: str(ref.get("canonical_key", "")),
    )


def _validate_contract_against_deps(signal_kind: str, resolved: list[dict[str, Any]]) -> None:
    if not resolved:
        # Description or dep-less request: implementation is deferred, nothing to check.
        return
    keys = [str(ref.get("canonical_key", "")) for ref in resolved]
    if signal_kind in _KINDS_REQUIRING_INDICATOR and not any(
        key.startswith(_INDICATOR_KEY_PREFIX) for key in keys
    ):
        raise OutputContractInvalid(
            f"A '{signal_kind}' candidate needs at least one indicator (ta.*) dependency."
        )
    if signal_kind in _KINDS_REQUIRING_CONDITION and not any(
        key.startswith(_CONDITION_KEY_PREFIX) for key in keys
    ):
        raise OutputContractInvalid(
            f"A '{signal_kind}' candidate needs at least one condition (cond.*) dependency."
        )


def _test_plan(signal_kind: str, resolved: list[dict[str, Any]]) -> list[str]:
    plan = [f"assert output kind == '{signal_kind}'"]
    for ref in resolved:
        key = str(ref.get("canonical_key", ""))
        plan.append(f"assert dependency '{key}' resolves to its pinned revision")
    return plan


def _uncertainty(source_kind: SourceKind, resolved: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    if source_kind == SourceKind.DESCRIPTION:
        notes.append(
            "Generated from a natural-language description; the implementation is a "
            "deterministic skeleton pending real code generation (Future-Dev)."
        )
    if not resolved:
        notes.append(
            "No declared dependencies resolved; the candidate declares no indicator "
            "or condition primitives."
        )
    return notes
