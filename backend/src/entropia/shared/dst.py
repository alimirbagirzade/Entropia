"""DST fold/gap adjudication (G8 / GH #559) — ONE rule, read by both normalizers.

Two production readers localize a naive wall clock under a declared source zone:

* ``domain.market_data.validation_rules._localize`` (ingest / approval), and
* ``domain.backtest.funding.parse_utc`` (funding schedule).

They are separate implementations, and their AGREEMENT is the real invariant — a
divergence would store a value at one instant and replay it at another
(``test_the_ingest_normalizer_and_the_funding_reader_agree_on_every_dst_case``). So the
rule lives here once and both call it; a second hand-written copy is how the two drift.

THE DECISION (signed by the PO, 2026-08-26 — `docs/decisions/closure_g8_dst_fold_gap_2026-08-25.md`)
-----------------------------------------------------------------------------------------------
**FOLD = A1 (accept).** A wall clock lived TWICE (2024-11-03 01:30 America/New_York is both
EDT -04:00 and EST -05:00). An offset-less source string cannot express which, ``fold``
defaults to 0, and the earlier instant wins. That is now a DECIDED behaviour, not a
characterization: the hour is genuinely ambiguous and picking the first occurrence is a
defensible answer to a real question.

**GAP = B2 (block).** A wall clock NEVER lived (2024-03-10 02:30 America/New_York — the
clock jumped 02:00 -> 03:00). There is no instant to choose, so normalizing it invents one.
The cell is reported UNRESOLVED and the revision cannot reach approval.

**The asymmetry is the whole decision and it was measured.** Fold has a defensible answer;
gap has none. ``A1 + B2`` is therefore cheaper and more coherent than blocking both, and
strictly better than the one combination the decision doc measured as INCONSISTENT
(``A2 + B1`` — blocking the defensible case while admitting the indefensible one).

**Scope = C1 (ingest / approval only).** Already-APPROVED revisions are untouched: they are
pinned into completed run manifests (doc 15 §15, INF-04/INF-05), and invalidating them would
change the inputs of shipped, immutable Results. No migration, no backfill, no re-analysis.

WHAT THIS DOES NOT DO (honest boundary)
---------------------------------------
It does not recover the folded hour's second occurrence. Nothing can: an offset-less string
cannot express ``fold=1``. That is the format's limit, not an implementation choice — so
under EVERY option that hour stays unaddressable. What changes here is only whether the
*gap* is silently invented or honestly refused.

Reach is narrow and was measured: only ``custom`` mode with a DST-observing IANA zone gets
here. ``exchange`` mode carries no IANA zone (already fail-closed), ``UTC`` has no DST, and
every engine-hot-path caller passes ``source_zone=None`` (naive already returns ``None``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

__all__ = ["is_nonexistent_local_time"]


def is_nonexistent_local_time(moment: datetime, zone: ZoneInfo) -> bool:
    """Did this NAIVE wall clock never occur in ``zone`` (a DST gap)?

    The PEP 495 round-trip: localize, convert to UTC, convert back. A real wall clock —
    including an AMBIGUOUS one — returns to itself, because both of a fold's two instants
    map back to the same local reading. An IMAGINARY one cannot: it lands on the far side
    of the jump and comes back as a DIFFERENT wall clock.

    That is exactly why this one predicate separates A1 from B2 without a second rule:
    ``False`` for a fold (which then resolves at ``fold=0``, the earlier instant) and
    ``True`` only for the gap. Callers pass a naive ``moment``; an aware value has already
    answered the question by carrying its own offset."""
    localized = moment.replace(tzinfo=zone)
    return localized.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != moment
