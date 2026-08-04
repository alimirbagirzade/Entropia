"""The ESP / Library / Agent-Tool-Gateway bodies are PUBLISHED, and published correctly.

A ``dict[str, Any]`` return keeps a response body invisible to ``docs/openapi.json`` while
the drift guard stays green, so the frontend has nothing to bind to — the trap O-30 closed
for the purge 202 and G-02 closed for the package export. This module asserts the same
thing for the eighteen surfaces typed in this slice, and pins the three properties that
make a published body safe rather than merely present:

* every response field is REQUIRED (nullability lives in the type, never in an absent key);
* state fields publish as plain ``string``, never a closed enum — an enum in a RESPONSE
  turns a value the server legitimately produced into a client-side validation failure;
* timestamps publish as plain ``string``, never ``format: date-time`` — the serializers
  already emit ``.isoformat()`` and a ``datetime`` field would re-render the value.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.apps.api.openapi_export import generate_schema

pytestmark = pytest.mark.contract

_API = "/api/v1"

# path -> (method, status, component name)
_TYPED_RESPONSES: dict[str, tuple[str, str, str]] = {
    f"{_API}/embedded-system-packages": ("post", "201", "CreateEspResponse"),
    f"{_API}/embedded-system-packages/{{entity_id}}": ("get", "200", "EspPackageDetailResponse"),
    f"{_API}/embedded-system-packages/{{entity_id}}/validate": (
        "post",
        "200",
        "EspValidationRunResponse",
    ),
    f"{_API}/embedded-system-packages/{{entity_id}}/activate": (
        "post",
        "200",
        "ActivateResolverResponse",
    ),
    f"{_API}/embedded-system-packages/{{entity_id}}/deprecate": (
        "post",
        "200",
        "DeprecateResolverResponse",
    ),
    f"{_API}/embedded-system-packages/resolve": ("post", "200", "ResolveDependencyResponse"),
    f"{_API}/library": ("get", "200", "LibraryPageResponse"),
    f"{_API}/library/{{entity_id}}": ("get", "200", "LibraryPackageDetailResponse"),
    f"{_API}/library/{{entity_id}}/deprecate": ("post", "200", "DeprecatePackageResponse"),
    f"{_API}/library/{{entity_id}}/derive": ("post", "201", "DerivePackageResponse"),
    f"{_API}/library/{{entity_id}}/revisions": ("post", "201", "CreatePackageRevisionResponse"),
    f"{_API}/library/{{entity_id}}/validation-runs": (
        "post",
        "201",
        "PackageValidationRunAcceptedResponse",
    ),
    f"{_API}/library/{{entity_id}}/request-approval": (
        "post",
        "200",
        "RequestPackageApprovalResponse",
    ),
    f"{_API}/library/{{entity_id}}/approve": ("post", "200", "ApprovePackageResponse"),
    f"{_API}/library/{{entity_id}}/export": ("post", "200", "PackageExportResponse"),
    f"{_API}/agent-tasks/{{task_id}}/tool-calls": ("get", "200", "AgentToolCallListResponse"),
    f"{_API}/agent-tool-calls/{{tool_call_id}}": ("get", "200", "AgentToolCallDetailResponse"),
}

# `_TYPED_RESPONSES` is keyed by PATH, so it can hold only one method per path. The ESP
# listing shares its path with the create POST, so it is asserted separately here. Any future
# second method on an already-listed path needs the same treatment — the blanket component
# walks below are what keep such a surface from going completely unchecked.
_ESP_LIST = (f"{_API}/embedded-system-packages", "get", "EspRegistryPageResponse")

# Timestamp fields are recognised by name: every serializer in scope emits its datetimes as
# pre-rendered ISO-8601 strings under one of these suffixes.
_TIMESTAMP_SUFFIXES = ("_at",)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return generate_schema()


def _component_for(schema: dict[str, Any], path: str, method: str, status: str) -> str:
    body = schema["paths"][path][method]["responses"][status]["content"]["application/json"]
    ref = body["schema"]["$ref"]
    return str(ref.rsplit("/", 1)[-1])


def _nullable_variants(prop: dict[str, Any]) -> list[dict[str, Any]]:
    """Unwrap the ``anyOf: [X, {type: null}]`` shape Pydantic emits for ``X | None``."""
    if "anyOf" in prop:
        return [v for v in prop["anyOf"] if v.get("type") != "null"]
    return [prop]


@pytest.mark.parametrize(("path", "spec"), sorted(_TYPED_RESPONSES.items()))
def test_the_response_body_is_published_as_a_named_component(
    schema: dict[str, Any], path: str, spec: tuple[str, str, str]
) -> None:
    method, status, component = spec
    assert _component_for(schema, path, method, status) == component
    assert component in schema["components"]["schemas"]


def test_the_esp_listing_publishes_its_page_envelope(schema: dict[str, Any]) -> None:
    path, method, component = _ESP_LIST
    assert _component_for(schema, path, method, "200") == component
    page = schema["components"]["schemas"][component]
    assert page["properties"]["data"]["items"]["$ref"].endswith("/EspRegistryEntry")
    assert page["properties"]["meta"]["$ref"].endswith("/CursorPageMeta")


def test_the_library_listing_and_detail_share_the_row_and_page_envelope(
    schema: dict[str, Any],
) -> None:
    page = schema["components"]["schemas"]["LibraryPageResponse"]
    assert page["properties"]["data"]["items"]["$ref"].endswith("/LibraryPackageRow")
    assert page["properties"]["meta"]["$ref"].endswith("/CursorPageMeta")
    row = set(schema["components"]["schemas"]["LibraryPackageRow"]["properties"])
    detail = set(schema["components"]["schemas"]["LibraryPackageDetailResponse"]["properties"])
    # The detail is a strict superset of the row on the WIRE, not just in Python.
    assert row <= detail


@pytest.mark.parametrize("component", sorted({c for _, _, c in _TYPED_RESPONSES.values()}))
def test_every_published_response_field_is_required(schema: dict[str, Any], component: str) -> None:
    model = schema["components"]["schemas"][component]
    assert set(model["required"]) == set(model["properties"]), (
        f"{component}: a response field that is not `required` advertises an omittable key. "
        "Nullability belongs in the type (`x: str | None`), never in a default."
    )


def test_nested_components_also_require_every_field(schema: dict[str, Any]) -> None:
    nested = [
        "CursorPageMeta",
        "EspRegistryEntry",
        "EspResolverContract",
        "EspValidationCheck",
        "EspValidationRunSummary",
        "LibraryPackageRow",
        "LiveRationaleFamilyRef",
        "PackagePermissionFlags",
        "PackageProvenance",
        "PackageProvenanceScan",
        "PackageRegistryObservation",
        "PackageRevisionSummary",
        "PinnedRationaleFamilyRef",
        "AgentToolCallCard",
    ]
    for component in nested:
        model = schema["components"]["schemas"][component]
        assert set(model["required"]) == set(model["properties"]), component


def _response_components(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every component reachable from a 2xx body of the surfaces this slice typed.

    Walked transitively so nested models are covered without a hand-maintained list — the
    list is what would silently stop covering a field someone adds later.
    """
    schemas = schema["components"]["schemas"]
    roots = {c for _, _, c in _TYPED_RESPONSES.values()} | {_ESP_LIST[2]}
    seen: dict[str, dict[str, Any]] = {}
    queue = list(roots)
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        model = schemas[name]
        seen[name] = model
        for prop in model.get("properties", {}).values():
            for ref in _refs_in(prop):
                queue.append(ref)
    return seen


def _refs_in(node: Any) -> list[str]:
    """Every ``$ref`` component name reachable from one property schema."""
    found: list[str] = []
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            found.append(ref.rsplit("/", 1)[-1])
        for value in node.values():
            found.extend(_refs_in(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_refs_in(item))
    return found


def test_no_published_response_field_is_a_closed_enum(schema: dict[str, Any]) -> None:
    """A closed enum in a RESPONSE turns a value the server legitimately produced into a
    client-side validation failure — and, because ``response_model`` validates on the way
    out, into a 500 first. The serializers emit lowercase ``StrEnum`` values as plain
    strings; the schema must say ``string``, not the member list.

    Walked over every reachable component rather than a hand-listed set of fields: the
    hand-list is exactly what stops covering the field somebody adds next.
    """
    offenders = [
        f"{name}.{field}"
        for name, model in _response_components(schema).items()
        for field, prop in model.get("properties", {}).items()
        for variant in _nullable_variants(prop)
        if "enum" in variant
    ]
    assert not offenders, f"closed enums published in a response body: {sorted(offenders)}"


def test_every_published_timestamp_is_a_plain_iso_string(schema: dict[str, Any]) -> None:
    """The serializers already emit ``.isoformat()``. A ``datetime`` field would re-parse and
    re-render the value, so no ``*_at`` field may carry a date-time format."""
    offenders = []
    for name, model in _response_components(schema).items():
        for field, prop in model.get("properties", {}).items():
            if not field.endswith(_TIMESTAMP_SUFFIXES):
                continue
            for variant in _nullable_variants(prop):
                if variant.get("type") != "string" or variant.get("format") is not None:
                    offenders.append(f"{name}.{field}={variant}")
    assert not offenders, f"timestamps not published as plain strings: {sorted(offenders)}"


def test_the_component_walk_actually_reaches_the_nested_models(schema: dict[str, Any]) -> None:
    """A walk that reached nothing would make the two tests above vacuously green."""
    reached = set(_response_components(schema))
    assert {
        "CursorPageMeta",
        "EspRegistryEntry",
        "EspResolverContract",
        "EspValidationRunSummary",
        "EspValidationCheck",
        "LibraryPackageRow",
        "PackagePermissionFlags",
        "PinnedRationaleFamilyRef",
        "LiveRationaleFamilyRef",
        "PackageProvenance",
        "PackageProvenanceScan",
        "PackageRevisionSummary",
        "PackageRegistryObservation",
        "AgentToolCallCard",
    } <= reached
    # Every reached component carries at least one property, i.e. the walk found real models.
    assert all(schema["components"]["schemas"][n].get("properties") for n in reached)


def test_the_open_payload_objects_stay_unconstrained(schema: dict[str, Any]) -> None:
    """Versioned / per-tool artifacts must publish as free-form objects.

    ``manifest`` states its own field set via ``export_schema_version`` and is round-tripped
    verbatim into ``POST /package-imports``; the gateway payloads are discriminated by
    ``tool_name`` across the whole tool registry. Closing either would drop fields.
    """
    schemas = schema["components"]["schemas"]
    manifest = schemas["PackageExportResponse"]["properties"]["manifest"]
    assert manifest.get("type") == "object" and "$ref" not in manifest
    request = schemas["AgentToolCallDetailResponse"]["properties"]["request"]
    assert request.get("type") == "object" and "$ref" not in request
    for variant in _nullable_variants(
        schemas["AgentToolCallDetailResponse"]["properties"]["response_ref"]
    ):
        assert variant.get("type") == "object" and "$ref" not in variant
    signature = schemas["EspResolverContract"]["properties"]["signature"]
    assert signature.get("type") == "object" and "$ref" not in signature


def test_registry_observation_is_now_typed_and_always_present(schema: dict[str, Any]) -> None:
    """G-02 shipped it as a bare object with a ``None`` default; it is a closed shape that
    ``_with_export_envelope_defaults`` guarantees is PRESENT (null at worst) on every reply,
    including a pre-G-02 idempotency replay. Typing + requiring it is a response
    tightening — strictly more guarantee for the client, never a removal."""
    export = schema["components"]["schemas"]["PackageExportResponse"]
    assert "registry_observation" in export["required"]
    variants = _nullable_variants(export["properties"]["registry_observation"])
    assert [v.get("$ref", "").rsplit("/", 1)[-1] for v in variants] == [
        "PackageRegistryObservation"
    ]


def test_the_error_envelope_is_untouched_by_this_slice(schema: dict[str, Any]) -> None:
    """O-02's envelope names never change; typing response bodies must not disturb them."""
    body = schema["components"]["schemas"]["ErrorBody"]
    assert set(body["properties"]) >= {
        "code",
        "message",
        "details",
        "request_id",
        "correlation_id",
        "category",
        "retryable",
        "suggested_action",
        "remediation",
        "scope_type",
        "scope_id",
        "field_path",
    }
    assert "ErrorResponse" in schema["components"]["schemas"]
