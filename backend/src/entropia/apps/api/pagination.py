"""Declare the ``limit`` query parameter for list endpoints that CLAMP it.

Two families of list endpoints ship in this API and they differ in how they treat a
``limit`` above the page ceiling:

* 19 parameters declare ``le=<max>``. FastAPI validates them, so an over-limit request
  is rejected with 422 and the ceiling is published as JSON Schema ``maximum``.
* 9 parameters -- this module's callers -- carry no ``le=`` and are bounded one layer
  down instead (``domain/agent_lab/cursor.py::clamp_limit``,
  ``queries/log_projection.py::_clamp_limit``,
  ``queries/panel_backtest_log.py::_clamp_limit``). An over-limit value is reduced to
  the ceiling and the request SUCCEEDS with a smaller page.

The clamping family published nothing at all -- no default, no ceiling -- so a client
could not learn either bound from ``docs/openapi.json`` (RC readiness finding P10-B2).
This module publishes both, and publishes them honestly: it deliberately does NOT emit
JSON Schema ``maximum``, because ``maximum`` asserts that larger values are invalid and
this server accepts them. Emitting it would trade an under-specified contract for a
false one -- a generated client would raise on a request the server answers 200. The
ceiling travels as ``x-clamp-maximum``, an extension no code generator can mistake for
a validation bound.

Scope note: WHETHER clamping or rejecting is the right over-limit behavior is a product
decision that no canonical page document settles. It is recorded as an open adjudication
in ``docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`` (section 6.7, P10-B2) and is
NOT decided here. This module publishes the behavior that ships today and changes none
of it.
"""

from __future__ import annotations

from typing import Any

from fastapi import Query


def clamped_limit_query(*, default: int, maximum: int) -> Any:
    """Build the ``limit`` query parameter for one clamping list endpoint.

    ``default`` and ``maximum`` are arguments rather than module constants because the
    three clamp helpers behind these endpoints do not share one default (20 / 25 / 50).
    A published bound that has drifted from the enforced one is worse than no bound at
    all, so every caller passes the constants its own query layer actually applies.
    """
    return Query(
        default=None,
        description=(
            f"Page size. Omitted -> {default}. A value above {maximum} is reduced to "
            f"{maximum}, and a value below 1 is raised to 1: an out-of-range limit is "
            "CLAMPED, not rejected, so the request still succeeds with a smaller page. "
            "The ceiling is published as `x-clamp-maximum` rather than as JSON Schema "
            "`maximum`, which would wrongly advertise that over-limit requests fail."
        ),
        json_schema_extra={"x-clamp-default": default, "x-clamp-maximum": maximum},
    )


__all__ = ["clamped_limit_query"]
