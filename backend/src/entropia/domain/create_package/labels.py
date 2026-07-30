"""Human display label for a Create-Package request (audit F-07 §4.4).

A Create-Package request carries **no user-assigned name**: doc 06 §4 gives the
package its display name only later, at the draft-metadata step after a candidate
exists (``package_request`` has no name column, and the draft's ``input_contract``
carries none either). So the Pre-Check request picker had nothing but the raw
``request_id`` to identify a row — recognizing an opaque identifier for a common
task, which F-07 forbids:

    *Required correction:* Add display DTOs at query boundaries; never reconstruct
    names from IDs in the browser. Keep copyable IDs in advanced detail.

``request_display_label`` composes the label the query boundary ships instead. It
is pure and deterministic — derived only from facts the request itself carries
(kind, revision attempt, creation instant) — so the same request always renders
the same text and the browser never invents one. The raw id stays alongside as the
secondary binding key (the D-4 name-primary / id-secondary convention).

The kind wording mirrors the frontend D-2 label map
(``lib/createPackage.ts::CREATE_PACKAGE_KIND_LABELS``); an unmapped kind falls back
to a title-cased render, so a new backend enum never surfaces as raw snake_case.
"""

from __future__ import annotations

from datetime import UTC, datetime

from entropia.domain.lifecycle.enums import PackageKind

_KIND_LABELS: dict[str, str] = {
    PackageKind.INDICATOR.value: "Indicator Package",
    PackageKind.CONDITION.value: "Condition Package",
    PackageKind.EMBEDDED_SYSTEM.value: "Embedded System Package",
    PackageKind.STRATEGY.value: "Strategy Package",
}

_SEGMENT_SEPARATOR = " · "
# Second precision, not minute: two requests of the same kind created inside one
# minute would otherwise share a label, and the label has to discriminate on its
# own — that is the whole point of not making the reader parse the ULID.
_CREATED_AT_FORMAT = "%Y-%m-%d %H:%M:%S UTC"


def package_kind_label(package_kind: PackageKind | str) -> str:
    """Human noun for a package kind — never a raw ``snake_case`` enum value."""
    value = str(package_kind)
    known = _KIND_LABELS.get(value)
    if known is not None:
        return known
    return value.replace("_", " ").title()


def request_display_label(
    *,
    package_kind: PackageKind | str,
    created_at: datetime | None,
    revision_attempt_no: int = 1,
) -> str:
    """Compose the request's primary human label.

    ``"Indicator Package · 2026-07-29 14:03:22 UTC"``, and with a revision attempt
    beyond the original ``"… · revision 2"`` (``revision_attempt_no`` is the attempt
    the request is ON, 1 = the original). ``created_at`` is the only discriminator a
    nameless request has, so it is omitted only when the row genuinely has none.
    """
    segments = [package_kind_label(package_kind)]
    if created_at is not None:
        segments.append(_utc_timestamp(created_at))
    if revision_attempt_no > 1:
        segments.append(f"revision {revision_attempt_no}")
    return _SEGMENT_SEPARATOR.join(segments)


def _utc_timestamp(moment: datetime) -> str:
    """Render the instant in UTC. A naive value is READ as UTC (the columns are
    ``timezone=True`` and the app writes UTC) — never shifted by the server's zone."""
    aware = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    return aware.strftime(_CREATED_AT_FORMAT)
