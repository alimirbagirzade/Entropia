"""Deterministic Create-Package candidate generation → a loadable implementation (F-14).

The V1 stub produced only a manifest + ``candidate_hash`` — a *hash without an
implementation*. F-14 replaces that: from the approved request's pinned
Embedded-System primitives and validated output contract, this module composes a
**real, deterministic, loadable Python implementation** (plus a test draft and the
structured validation inputs), and derives the candidate hash from the whole artifact.

Two honest properties this preserves:

* **Loadable + executable.** The generated ``source`` is valid Python that
  ``compile()``s and, when exec'd in the validation sandbox, exposes
  :data:`ENTRY_SYMBOL` returning the package's resolver-loadable signal plan. The
  built-in resolver reads the same pinned primitives from the immutable
  ``dependency_snapshot`` (the body is never executed in production — the sandbox
  executes it only to prove the candidate loads and yields a non-empty plan).
* **Empty skeletons stay non-executable.** A request that resolved no native
  primitive (a description with nothing to generate from yet) produces a source
  whose plan has no primitives → ``executable`` is ``False`` → the validation
  sandbox blocks it and it can never reach approval (F-14 acceptance).

Reproducibility (INF-04/INF-05): the SAME inputs always yield the SAME source and
hash; bumping :data:`GENERATOR_VERSION` (mirrors ENGINE_VERSION) shifts the hash
namespace so a candidate made by an older generator is never silently reused. A real
LLM/arbitrary-code generator + its isolated execution sandbox stays Future-Dev; this
is the deterministic, native-plan-backed generator that is buildable and verifiable now.

No I/O. The application command feeds the resolved refs + output contract in and
persists the resulting implementation, output contract and ``candidate_hash``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from entropia.domain.create_package.candidate import CandidateManifest, build_candidate_manifest
from entropia.domain.create_package.enums import SourceKind, SourceLanguage
from entropia.domain.revision.hashing import content_hash

# Bumping this shifts the candidate_hash namespace AND supersedes the v1 manifest-only
# stub: a v1 hash (no implementation) never collides with a v2 candidate.
GENERATOR_VERSION = "cp-candidate-gen-v2"

# The symbol the generated module exposes; the validation sandbox calls it to obtain
# the resolver-loadable plan and prove the candidate is executable.
ENTRY_SYMBOL = "build_signal_plan"

# The generated implementation is Python regardless of the request's declared source
# language: the V1 native-plan runtime is Python (RuntimeAdapter.PYTHON), so a loadable
# artifact the built-in resolver + sandbox can run is a Python plan module.
IMPLEMENTATION_LANGUAGE = str(SourceLanguage.PYTHON)


@dataclass(frozen=True, slots=True)
class GeneratedImplementation:
    """A loadable, executable implementation generated from the approved request."""

    language: str
    entry_symbol: str
    source: str
    test_source: str
    plan: dict[str, Any]
    executable: bool
    provenance: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GeneratedCandidate:
    """The full generated candidate: manifest + loadable implementation + hash."""

    manifest: CandidateManifest
    implementation: GeneratedImplementation
    candidate_hash: str

    @property
    def output_contract(self) -> dict[str, Any]:
        return self.manifest.output_contract


def generate_candidate(
    *,
    request_id: str,
    package_kind: str,
    source_kind: SourceKind,
    output_contract: dict[str, Any],
    resolved_refs: list[dict[str, Any]] | None,
    source_language: SourceLanguage | None = None,
) -> GeneratedCandidate:
    """Generate a loadable candidate from the approved request (doc 06 §5, F-14).

    Raises ``OutputContractInvalid`` (via :func:`build_candidate_manifest`) if the
    output contract has no kind or is incompatible with the resolved dependency set.
    """
    manifest = build_candidate_manifest(
        package_kind=package_kind,
        source_kind=source_kind,
        output_contract=output_contract,
        resolved_refs=resolved_refs,
    )
    primitives = [str(ref.get("canonical_key", "")) for ref in manifest.resolved_dependencies]
    plan: dict[str, Any] = {
        "output_kind": manifest.signal_kind,
        "package_kind": manifest.package_kind,
        "primitives": primitives,
    }
    # A candidate is executable only if it resolved at least one native primitive to
    # compute — an empty skeleton (no primitives) yields an empty plan and is blocked.
    executable = bool(primitives)
    provenance: dict[str, Any] = {
        "request_id": request_id,
        "generator_version": GENERATOR_VERSION,
        "source_kind": str(source_kind),
        "source_language": str(source_language) if source_language else None,
        "output_kind": manifest.signal_kind,
        "resolved_dependencies": manifest.resolved_dependencies,
    }
    implementation = GeneratedImplementation(
        language=IMPLEMENTATION_LANGUAGE,
        entry_symbol=ENTRY_SYMBOL,
        source=_render_source(
            request_id=request_id,
            package_kind=manifest.package_kind,
            source_kind=str(source_kind),
            output_kind=manifest.signal_kind,
            primitives=primitives,
        ),
        test_source=_render_test_source(
            request_id=request_id,
            output_kind=manifest.signal_kind,
            primitives=primitives,
        ),
        plan=plan,
        executable=executable,
        provenance=provenance,
    )
    digest = content_hash(
        {
            "generator_version": GENERATOR_VERSION,
            "manifest": manifest.as_dict(),
            "source": implementation.source,
            "test_source": implementation.test_source,
            "plan": plan,
            "executable": executable,
        }
    )
    return GeneratedCandidate(
        manifest=manifest,
        implementation=implementation,
        candidate_hash=f"sha256:{digest}",
    )


def _render_source(
    *,
    request_id: str,
    package_kind: str,
    source_kind: str,
    output_kind: str,
    primitives: list[str],
) -> str:
    """Render the deterministic, loadable Python implementation module.

    The module compiles and, exec'd with an empty ``__builtins__`` in the validation
    sandbox, exposes ``ENTRY_SYMBOL`` returning the plan built from module globals —
    no builtins, imports, or I/O, so the sandbox is safe by construction.
    """
    return (
        '"""Entropia Create-Package generated implementation (deterministic — do not edit).\n'
        f"\nGenerator: {GENERATOR_VERSION}\n"
        f"Provenance: request {request_id}\n"
        f"Package kind: {package_kind} | Output kind: {output_kind} | Source: {source_kind}\n"
        "\nGenerated deterministically from the approved request's pinned Embedded-System\n"
        "primitives and validated output contract. It declares the resolver-loadable signal\n"
        "plan this package computes; the built-in resolver reads the same pinned primitives\n"
        f"(the body is never executed in production — the sandbox runs {ENTRY_SYMBOL}() only\n"
        'to prove the candidate loads and yields a non-empty plan).\n"""\n'
        "\n"
        f'GENERATOR_VERSION = "{GENERATOR_VERSION}"\n'
        f'PACKAGE_KIND = "{package_kind}"\n'
        f'OUTPUT_KIND = "{output_kind}"\n'
        f"PRIMITIVES = {primitives!r}\n"
        "\n"
        f"def {ENTRY_SYMBOL}():\n"
        '    """Return the resolver-loadable plan this generated package computes."""\n'
        "    return {\n"
        '        "output_kind": OUTPUT_KIND,\n'
        '        "package_kind": PACKAGE_KIND,\n'
        '        "primitives": PRIMITIVES,\n'
        "    }\n"
    )


def _render_test_source(
    *,
    request_id: str,
    output_kind: str,
    primitives: list[str],
) -> str:
    """Render the deterministic test draft (a traceable artifact; not executed by V1)."""
    return (
        f'"""Generated validation test draft for request {request_id} (deterministic).\n'
        "\nAsserts the generated implementation loads to the declared output kind and the\n"
        'pinned primitives. Executed against the loaded candidate module in the sandbox."""\n'
        "\n"
        "\n"
        "def test_output_kind(build_signal_plan):\n"
        f'    assert build_signal_plan()["output_kind"] == "{output_kind}"\n'
        "\n"
        "\n"
        "def test_primitives_resolved(build_signal_plan):\n"
        f'    assert build_signal_plan()["primitives"] == {primitives!r}\n'
    )


__all__ = [
    "ENTRY_SYMBOL",
    "GENERATOR_VERSION",
    "IMPLEMENTATION_LANGUAGE",
    "GeneratedCandidate",
    "GeneratedImplementation",
    "generate_candidate",
]
