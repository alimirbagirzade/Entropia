"""Every ``limit`` query parameter publishes its page ceiling (RC finding P10-B2).

Two families ship, and the difference between them is a PRODUCT decision this test
deliberately does not make -- it only forces both to be visible in the schema:

* ENFORCING (19 params): ``le=<max>`` -> JSON Schema ``maximum`` -> over-limit is 422.
* CLAMPING (9 params): bounded in the query layer -> over-limit is 200 with a smaller
  page. Published as ``x-clamp-maximum`` by ``apps/api/pagination.py``.

Before this gate the clamping family published NOTHING: a client reading
``docs/openapi.json`` could not learn the default or the ceiling, and ``limit=100000``
came back 200 with 100 rows. The tests below lock three things:

1. no ``limit`` parameter is unpublished (the gate itself -- a new list endpoint that
   forgets to declare its bound fails here, not in a later readiness audit);
2. a clamping parameter never emits ``maximum`` -- that keyword promises rejection, and
   advertising a rejection the server does not perform is worse than publishing nothing;
3. the published numbers equal the ones the query layer actually enforces.

The over-limit BEHAVIOR is unchanged by this slice and is pinned as such below. Whether
clamping or rejecting is correct is an open adjudication for the product owner, recorded
in ``docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`` section 6.7 (P10-B2).
"""

from __future__ import annotations

from typing import Any

from entropia.application.queries.log_projection import DEFAULT_LOG_LIMIT, MAX_LOG_LIMIT
from entropia.application.queries.panel_backtest_log import (
    DEFAULT_BACKTEST_LOG_LIMIT,
    MAX_BACKTEST_LOG_LIMIT,
)
from entropia.apps.api.openapi_export import generate_schema
from entropia.domain.agent_lab.cursor import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, clamp_limit

#: The clamping family: path -> (published default, published ceiling). Each pair is the
#: constant its own query layer applies, so a drift between enforced and published fails.
CLAMPING_ENDPOINTS: dict[str, tuple[int, int]] = {
    "/api/v1/admin/users": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
    "/api/v1/admin/backtest-logs": (DEFAULT_BACKTEST_LOG_LIMIT, MAX_BACKTEST_LOG_LIMIT),
    "/api/v1/admin/logs": (DEFAULT_LOG_LIMIT, MAX_LOG_LIMIT),
    "/api/v1/agent-tasks": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
    "/api/v1/agent-tasks/{task_id}/tool-calls": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
    "/api/v1/lab/messages": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
    "/api/v1/hypotheses": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
    "/api/v1/view-datasets": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
    "/api/v1/analysis-artifacts": (DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
}


def _limit_parameters() -> list[tuple[str, dict[str, Any]]]:
    """Every published ``limit`` query parameter as ``(path, parameter schema)``."""
    found: list[tuple[str, dict[str, Any]]] = []
    for path, operations in generate_schema()["paths"].items():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters", []):
                if parameter.get("name") == "limit" and parameter.get("in") == "query":
                    found.append((path, parameter.get("schema", {})))
    return found


def _json_schema_maximum(schema: dict[str, Any]) -> int | None:
    """Read ``maximum`` from the schema, or from an ``anyOf`` branch.

    An OPTIONAL constrained parameter (``int | None`` with ``le=``) puts the bound inside
    ``anyOf``, not at the top level. A check that only reads the top level would score
    those endpoints as unpublished and hide the real gap behind false failures.
    """
    if "maximum" in schema:
        maximum = schema["maximum"]
        assert isinstance(maximum, int)
        return maximum
    for branch in schema.get("anyOf", []):
        if isinstance(branch, dict) and "maximum" in branch:
            maximum = branch["maximum"]
            assert isinstance(maximum, int)
            return maximum
    return None


def test_every_limit_parameter_publishes_a_ceiling() -> None:
    """The P10-B2 gate: no ``limit`` may leave its bound out of the contract."""
    unpublished = [
        path
        for path, schema in _limit_parameters()
        if _json_schema_maximum(schema) is None and "x-clamp-maximum" not in schema
    ]
    assert not unpublished, (
        "these `limit` parameters publish no page ceiling — declare `le=<max>` when the "
        "endpoint REJECTS an over-limit value, or "
        "`apps/api/pagination.py::clamped_limit_query` when it CLAMPS: " + repr(unpublished)
    )


def test_the_two_families_partition_every_limit_parameter() -> None:
    """Enforcing and clamping are exclusive: 19 + 9, with no parameter in both."""
    parameters = _limit_parameters()
    enforcing = [p for p, s in parameters if _json_schema_maximum(s) is not None]
    clamping = [p for p, s in parameters if "x-clamp-maximum" in s]

    assert sorted(clamping) == sorted(CLAMPING_ENDPOINTS), (
        "the clamping family changed — update CLAMPING_ENDPOINTS with the enforced "
        "constants, so published and enforced bounds cannot drift apart"
    )
    assert len(enforcing) + len(clamping) == len(parameters)
    assert not set(enforcing) & set(clamping)


def test_a_clamping_parameter_never_advertises_rejection() -> None:
    """``maximum`` means "larger values are invalid" — these endpoints accept them.

    Emitting it would trade an under-specified contract for a false one: a generated
    client would refuse a request this server answers 200.
    """
    for path, schema in _limit_parameters():
        if "x-clamp-maximum" not in schema:
            continue
        assert _json_schema_maximum(schema) is None, f"{path} advertises a bound it does not apply"
        assert "exclusiveMaximum" not in schema, path


def test_published_bounds_equal_the_enforced_bounds() -> None:
    """A published number that has drifted from the applied one is worse than none."""
    published = {
        path: schema for path, schema in _limit_parameters() if "x-clamp-maximum" in schema
    }
    for path, (expected_default, expected_maximum) in CLAMPING_ENDPOINTS.items():
        schema = published[path]
        assert schema["x-clamp-default"] == expected_default, path
        assert schema["x-clamp-maximum"] == expected_maximum, path


def test_publishing_the_ceiling_did_not_change_the_over_limit_behaviour() -> None:
    """This slice publishes the shipped clamp; it does not decide clamp-vs-reject.

    If a later change makes the clamping family REJECT instead, this pin fails and forces
    the product decision to be recorded rather than absorbed as a refactor side effect.
    """
    assert clamp_limit(MAX_PAGE_LIMIT + 1) == MAX_PAGE_LIMIT
    assert clamp_limit(100_000) == MAX_PAGE_LIMIT
    assert clamp_limit(0) == 1
    assert clamp_limit(None) == DEFAULT_PAGE_LIMIT
