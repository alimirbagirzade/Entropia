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

The split is a PRODUCT-OWNER DECISION of 2026-08-12 (see below), not an oversight.

The clamping family published nothing at all -- no default, no ceiling -- so a client
could not learn either bound from ``docs/openapi.json`` (RC readiness finding P10-B2).
This module publishes both, and publishes them honestly: it deliberately does NOT emit
JSON Schema ``maximum``, because ``maximum`` asserts that larger values are invalid and
this server accepts them. Emitting it would trade an under-specified contract for a
false one -- a generated client would raise on a request the server answers 200. The
ceiling travels as ``x-clamp-maximum``, an extension no code generator can mistake for
a validation bound.

WHETHER clamping or rejecting is the right over-limit behavior is a product decision that
no canonical page document settles. ADIM 37 published the bound and left the question
open; **the product owner decided on 2026-08-12 that the clamping family KEEPS clamping**
and is not converted to 422. Two reasons, both recorded so the next reader does not file
the split as an inconsistency for a third time:

* the behavior is no longer SILENT. The gap worth closing was that a client could not
  learn either bound from ``docs/openapi.json``; ``x-clamp-default`` / ``x-clamp-maximum``
  closed that, and an under-specified contract was the actual defect, not the clamp.
* converting would BREAK GENERATED CLIENTS. A request that answers 200 today would start
  being rejected — a shipped wire contract cannot be re-cut for symmetry alone.

So the two families are a DELIBERATE split, not a drift: 19 parameters ENFORCE (JSON
Schema ``maximum`` -> 422), 9 CLAMP (``x-clamp-maximum`` -> 200). The three different
defaults are deliberate too (20 / 25 / 50, ceiling 100 in all three) — each is the
constant its own query layer applies. Recorded in
``docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`` section 6.7 (P10-B2, §6.7.5) and
pinned by ``tests/contract/test_pagination_limit_contract.py``.
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
