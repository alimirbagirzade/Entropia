"""The frontend wire interfaces and the published OpenAPI schema state the SAME contract.

Typing a response body is only half the job: if ``frontend/src/lib/*.ts`` declares a field
the server never sends — or omits one it always sends, or disagrees about whether a value
may be ``null`` — then the client is deriving its own truth and the published schema is
decoration. This test is the machine check for that, in the same spirit as the F-05
capability-matrix mirror (``tests/unit/test_capability_matrix.py``), which already reads a
frontend file from the Python side.

It caught a real drift on the way in: ``EspPackageDetail`` had never declared
``latest_validation_run``, which the server has sent since R8.

The parser is deliberately small and strict. It understands exactly the subset the wire
modules use — ``export interface X [extends Y | Omit<Y, "f">] { name[?]: Type; }`` — and
raises rather than guessing, so a syntax it cannot read fails the test instead of silently
passing it. Nullability is read from the TS union; OPTIONALITY is not compared, because the
server side is asserted to be all-required by ``test_typed_contract_openapi.py``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from entropia.apps.api.openapi_export import generate_schema

pytestmark = pytest.mark.contract

_FRONTEND_LIB = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib"

# OpenAPI component  <->  (wire module, TypeScript interface)
_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("EspRegistryEntry", "esp", "EspRegistryRow"),
    ("EspResolverContract", "esp", "EspContract"),
    ("EspValidationRunSummary", "esp", "EspValidationRunSummary"),
    ("EspPackageDetailResponse", "esp", "EspPackageDetail"),
    ("ResolveDependencyResponse", "esp", "ResolveResult"),
    ("CreateEspResponse", "esp", "CreateEspResult"),
    ("ActivateResolverResponse", "esp", "ActivateResolverResult"),
    ("DeprecateResolverResponse", "esp", "DeprecateResolverResult"),
    ("PackagePermissionFlags", "library", "PackagePermissions"),
    ("PinnedRationaleFamilyRef", "library", "PinnedFamilyRef"),
    ("LiveRationaleFamilyRef", "library", "LiveRationaleFamily"),
    ("PackageProvenanceScan", "library", "ProvenanceScan"),
    ("PackageProvenance", "library", "PackageProvenance"),
    ("PackageRevisionSummary", "library", "RevisionSummary"),
    ("LibraryPackageRow", "library", "LibraryPackageRow"),
    ("LibraryPackageDetailResponse", "library", "LibraryPackageDetail"),
    ("DeprecatePackageResponse", "library", "DeprecatePackageResult"),
    ("DerivePackageResponse", "library", "DerivePackageResult"),
    ("CreatePackageRevisionResponse", "library", "CreateRevisionResult"),
    ("RequestPackageApprovalResponse", "library", "RequestApprovalResult"),
    ("ApprovePackageResponse", "library", "ApprovePackageResult"),
    ("PackageRegistryObservation", "library", "RegistryObservation"),
    ("PackageExportResponse", "library", "ExportPackageResult"),
    ("PackageValidationRunAcceptedResponse", "library", "RequestValidationResult"),
    ("AgentToolCallCard", "agentLab", "AgentToolCallCard"),
    ("AgentToolCallDetailResponse", "agentLab", "AgentToolCallDetail"),
    ("AgentToolCallListResponse", "agentLab", "AgentToolCallList"),
)

# `unknown` is the TS escape hatch for a JSONB payload the client must not narrow
# (`resolved_refs`, `missing_calls`, `unsupported_calls`). It carries no nullability
# claim either way, so those fields are compared by NAME only.
_UNKNOWN_TS_TYPE = "unknown"


def _source(module: str) -> str:
    path = _FRONTEND_LIB / f"{module}.ts"
    assert path.exists(), f"missing wire module: {path}"
    return path.read_text(encoding="utf-8")


def _interface_body(source: str, name: str) -> tuple[str | None, str]:
    """Return ``(extends_clause, body)`` for one ``export interface``."""
    start = re.search(rf"export interface {re.escape(name)}\b", source)
    if start is None:
        raise AssertionError(f"interface {name} not found")
    brace = source.index("{", start.end())
    header = source[start.end() : brace]
    depth, i = 1, brace + 1
    while depth:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    extends = header.split("extends", 1)[1] if "extends" in header else None
    return (" ".join(extends.split()) if extends else None, source[brace + 1 : i - 1])


def _ts_fields(module: str, name: str) -> dict[str, dict[str, Any]]:
    source = _source(module)
    extends, body = _interface_body(source, name)
    fields: dict[str, dict[str, Any]] = {}
    if extends:
        omit = re.fullmatch(r'Omit<\s*(\w+)\s*,\s*"([^"]+)"\s*>', extends)
        if omit:
            parent = _ts_fields(module, omit.group(1))
            fields.update({k: v for k, v in parent.items() if k != omit.group(2)})
        elif re.fullmatch(r"\w+", extends):
            fields.update(_ts_fields(module, extends))
        else:
            raise AssertionError(f"unsupported extends clause on {name}: {extends!r}")
    for line in body.splitlines():
        line = line.split("//")[0].strip()
        match = re.fullmatch(r"(\w+)(\??):\s*(.+?);", line)
        if match:
            declared = match.group(3).strip()
            fields[match.group(1)] = {
                "nullable": any(part.strip() == "null" for part in declared.split("|")),
                "opaque": declared == _UNKNOWN_TS_TYPE,
            }
    return fields


def _schema_fields(schema: dict[str, Any], component: str) -> dict[str, dict[str, Any]]:
    model = schema["components"]["schemas"][component]
    return {
        name: {"nullable": any(v.get("type") == "null" for v in prop.get("anyOf", []))}
        for name, prop in model.get("properties", {}).items()
    }


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return generate_schema()


@pytest.mark.parametrize(("component", "module", "interface"), _PAIRS)
def test_the_typescript_interface_mirrors_the_published_component(
    schema: dict[str, Any], component: str, module: str, interface: str
) -> None:
    server = _schema_fields(schema, component)
    client = _ts_fields(module, interface)

    assert set(server) == set(client), (
        f"{component} <-> {module}.ts::{interface} field drift.\n"
        f"  server-only (add to the TS interface): {sorted(set(server) - set(client))}\n"
        f"  client-only (the server never sends these): {sorted(set(client) - set(server))}"
    )
    mismatched = {
        name
        for name in server
        if not client[name]["opaque"] and server[name]["nullable"] != client[name]["nullable"]
    }
    assert not mismatched, (
        f"{component} <-> {module}.ts::{interface} nullability drift on {sorted(mismatched)}: "
        "a TS type narrower than the server is a latent runtime bug; wider is a dead branch."
    )


def test_a_missing_interface_is_loud() -> None:
    """A parser that silently returned ``{}`` for a renamed interface would turn drift into
    a green test. A field LINE it cannot parse is skipped rather than raised on — that stays
    fail-loud through the set comparison above, which is why only this path raises."""
    with pytest.raises(AssertionError):
        _ts_fields("esp", "NoSuchInterfaceName")


def test_every_pair_actually_parsed_some_fields() -> None:
    """The set comparison is only meaningful if BOTH sides are non-empty. An interface the
    parser silently read as empty would still fail the comparison — but an OpenAPI component
    with no properties would make it vacuously pass, so both sides are checked here."""
    from entropia.apps.api.openapi_export import generate_schema

    published = generate_schema()
    for component, module, interface in _PAIRS:
        assert _ts_fields(module, interface), f"{module}.ts::{interface} parsed as empty"
        assert _schema_fields(published, component), f"{component} published no properties"
