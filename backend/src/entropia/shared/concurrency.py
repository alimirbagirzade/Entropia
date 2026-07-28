"""Optimistic concurrency helpers (DOMAIN_MODEL §10).

Every mutation carries an expected token (`expected_row_version` or
`expected_head_revision_id`), mirrored by HTTP `If-Match`/`ETag`. A mismatch is a
409 STALE_REVISION — never last-write-wins.

**Dual-token rule (O-12).** Some endpoints accept the same token in *two* places:
the request body (`expected_*`, the domain identity) and the `If-Match` header (the
HTTP transport of that identity). They are two spellings of ONE value, never two
independent preconditions — doc 15 §11, doc 20 §14, doc 21 §7. Supply either, or
both in agreement; supplying both with *different* values is a 409
`OCC_TOKEN_CONFLICT`. Every dual-token route resolves through
:func:`reconcile_occ_tokens` so the rule is stated once and cannot drift.
"""

from __future__ import annotations

from typing import TypeVar

from entropia.shared.errors import OccTokenConflictError, StaleRevisionError

OccToken = TypeVar("OccToken", int, str)


def check_row_version(actual: int, expected: int | None) -> None:
    if expected is not None and actual != expected:
        raise StaleRevisionError(f"Expected row_version {expected} but current is {actual}.")


def check_head_revision(actual: str | None, expected: str | None) -> None:
    if expected is not None and actual != expected:
        raise StaleRevisionError("The resource head revision changed. Refresh and retry.")


def etag_for_row_version(row_version: int) -> str:
    """Strong ETag derived from a root's row_version."""
    return f'"rv-{row_version}"'


def row_version_from_if_match(if_match: str | None) -> int | None:
    """Parse an If-Match header produced by etag_for_row_version()."""
    if not if_match:
        return None
    value = if_match.strip().strip('"')
    if value.startswith("rv-"):
        value = value[3:]
    try:
        return int(value)
    except ValueError:
        return None


def reconcile_occ_tokens(
    body_value: OccToken | None,
    header_value: OccToken | None,
    *,
    field: str,
) -> OccToken | None:
    """Collapse the body + ``If-Match`` OCC tokens into the one value they must share.

    The single dual-token rule (O-12). ``header_value`` is the ``If-Match`` header
    already parsed into the SAME domain shape as ``body_value`` (an ``int`` row
    version, or a ``str`` revision id / fingerprint) — this function compares domain
    values, never raw header text.

    * only one supplied -> that one wins (either spelling is a complete precondition)
    * both supplied and equal -> that value (the transport simply mirrored the body)
    * both supplied and different -> 409 ``OCC_TOKEN_CONFLICT``
    * neither supplied -> ``None`` (the caller decides whether a token is mandatory)

    The body keeps its historical precedence in the agreeing case, so no existing
    single-token caller changes behaviour; only the previously *undefined*
    disagreement case becomes an explicit, uniform failure.
    """
    if body_value is None:
        return header_value
    if header_value is None:
        return body_value
    if body_value != header_value:
        raise OccTokenConflictError(
            details=[
                {
                    "field": field,
                    "body_value": str(body_value),
                    "if_match_value": str(header_value),
                }
            ],
            field_path=field,
        )
    return body_value
