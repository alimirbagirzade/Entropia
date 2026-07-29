"""OpenAPI contract + drift guard (GAP-19).

Two guarantees enforced by the test suite (belt-and-suspenders with the CI
``--check`` step):

* the app's generated schema is a valid OpenAPI 3.1 document, and
* the committed snapshot ``docs/openapi.json`` matches the freshly generated
  schema — so any HTTP-surface change that forgets to regenerate the snapshot
  fails locally under ``pytest``, not only in CI.
"""

from __future__ import annotations

from openapi_spec_validator import validate

from entropia.apps.api.openapi_export import (
    SNAPSHOT_PATH,
    _check,
    generate_schema,
    main,
    render_schema,
    write_snapshot,
)


def test_purge_202_publishes_both_state_field_names() -> None:
    """O-30: the adjudicated purge body must be VISIBLE in the schema.

    While the handler returned a bare ``dict``, the drift guard could stay green
    while the schema said nothing at all about this contract — a green guard was
    not evidence the fields shipped. This test is what closes that gap: it reads
    the published 202 component and fails if either spelling disappears.
    """
    schema = generate_schema()
    purge = schema["paths"]["/api/v1/trash-entries/{trash_entry_id}/purge"]["post"]
    ref = purge["responses"]["202"]["content"]["application/json"]["schema"]["$ref"]
    component = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]

    # Both names, because doc 20 §4/§7 and §9.2 each have a reader (see
    # routes/trash.py::PurgeAcceptedResponse).
    assert "deletion_state" in component["properties"]
    assert "root_lifecycle_state" in component["properties"]
    assert "root_lifecycle_state" in component["required"], "the §4/§7 name is not optional"


def test_openapi_schema_is_valid() -> None:
    # Raises OpenAPIValidationError if the generated document is malformed.
    validate(generate_schema())


def test_openapi_snapshot_is_current() -> None:
    assert SNAPSHOT_PATH.exists(), f"missing snapshot: {SNAPSHOT_PATH}"
    expected = render_schema(generate_schema())
    actual = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert actual == expected, "docs/openapi.json is stale — run `make openapi` and commit it."


def test_render_is_deterministic() -> None:
    assert render_schema(generate_schema()) == render_schema(generate_schema())


def test_check_mode_passes_against_committed_snapshot() -> None:
    assert main(["--check"]) == 0


def test_write_then_check_roundtrip(tmp_path) -> None:
    target = tmp_path / "openapi.json"
    write_snapshot(target)
    assert _check(target) == 0
    # A mutated snapshot is detected as stale.
    target.write_text("{}\n", encoding="utf-8")
    assert _check(target) == 1
