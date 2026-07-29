"""Lock the Admin Logs time-window, free-text and keyset axes (doc 19 §4.3, §5, §6.2).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

``queries/log_projection.py::list_log_events`` is the compliance read surface. Its
family / severity / actor_type / actor_id / correlation_id axes are covered by
``test_panel_management_logs.py::test_logs_filters`` and
``test_log_resource_types.py``, but three axes shipped with NO test at all:
``from_at``, ``to_at`` and ``query_text``. Their failure mode is silent in the worst
direction for an audit — a broken bound or a mis-built OR returns a SHORTER page, so
an auditor sees fewer events with no error to notice.

Two more unguarded branches are pinned here for the same reason:

* the composite keyset tie-break (``occurred_at == last_at AND event_id < ...``) —
  the existing pagination test seeds events one minute apart, so the equal-time leg
  that stops a page from repeating or skipping an event never executes;
* ``_clamp_limit`` — an unclamped ``limit`` would let one request pull the whole
  history the module's docstring promises it never ships.

Behaviour is unchanged; this only makes a regression loud.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from entropia.application.queries.log_projection import (
    DEFAULT_LOG_LIMIT,
    MAX_LOG_LIMIT,
    list_log_events,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role
from entropia.infrastructure.postgres.models import AuditEvent
from entropia.shared.errors import AdminPanelAccessRequiredError

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_BASE_TIME = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

# ``MAX_QUERY_TEXT`` in the module under test; kept as a literal so a change to the
# shipped cap has to be made deliberately in two places.
_MAX_QUERY_TEXT = 128


def _seed(
    session,
    *,
    event_id: str,
    occurred_at: datetime,
    kind: str = "user.role_assigned",
    severity: str = "info",
    reason: str | None = None,
    target_id: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            event_id=event_id,
            occurred_at=occurred_at,
            event_kind=kind,
            severity=severity,
            actor_principal_id="user_admin",
            actor_kind=ActorKind.HUMAN,
            target_entity_id=target_id,
            reason=reason,
        )
    )


def _ids(page: dict) -> list[str]:
    return [row["event_id"] for row in page["data"]]


# --------------------------------------------------------------------------- #
# Time window: from_at / to_at                                                 #
# --------------------------------------------------------------------------- #


async def test_from_at_includes_an_event_occurring_exactly_on_the_bound(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN, from_at=_BASE_TIME)

    assert _ids(page) == ["evt_0001"]


async def test_to_at_includes_an_event_occurring_exactly_on_the_bound(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN, to_at=_BASE_TIME)

    assert _ids(page) == ["evt_0001"]


async def test_from_at_excludes_events_older_than_the_bound(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME - timedelta(seconds=1))
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN, from_at=_BASE_TIME)

    assert _ids(page) == ["evt_0002"]


async def test_to_at_excludes_events_newer_than_the_bound(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME + timedelta(seconds=1))
    await session.commit()

    page = await list_log_events(session, ADMIN, to_at=_BASE_TIME)

    assert _ids(page) == ["evt_0001"]


async def test_from_and_to_together_return_only_the_closed_window_newest_first(session) -> None:
    for index in range(5):
        _seed(
            session,
            event_id=f"evt_{index:04d}",
            occurred_at=_BASE_TIME + timedelta(minutes=index),
        )
    await session.commit()

    page = await list_log_events(
        session,
        ADMIN,
        from_at=_BASE_TIME + timedelta(minutes=1),
        to_at=_BASE_TIME + timedelta(minutes=3),
    )

    assert _ids(page) == ["evt_0003", "evt_0002", "evt_0001"]


async def test_returns_an_empty_page_when_the_window_holds_no_event(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(
        session,
        ADMIN,
        from_at=_BASE_TIME + timedelta(days=1),
        to_at=_BASE_TIME + timedelta(days=2),
    )

    assert page["data"] == []
    assert page["meta"]["has_more"] is False


# --------------------------------------------------------------------------- #
# Free-text search: query_text                                                 #
# --------------------------------------------------------------------------- #


async def test_query_text_matches_the_event_kind_case_insensitively(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME, kind="backtest.run_failed")
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME, kind="user.role_assigned")
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="RUN_FAILED")

    assert _ids(page) == ["evt_0001"]


async def test_query_text_matches_the_subject_id(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME, target_id="strat_needle")
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME, target_id="strat_other")
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="needle")

    assert _ids(page) == ["evt_0001"]


async def test_query_text_matches_the_reason_text(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME, reason="Demoted by policy review")
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME, reason="Routine promotion")
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="policy review")

    assert _ids(page) == ["evt_0001"]


async def test_query_text_matching_no_searched_field_returns_an_empty_page(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME, reason="Routine promotion")
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="no-such-token")

    assert page["data"] == []
    assert page["meta"]["has_more"] is False


async def test_query_text_does_not_search_unadvertised_columns(session) -> None:
    # Only event_kind / target_entity_id / reason are searched; the actor id is not,
    # so a caller cannot use ``q`` as an undocumented actor filter.
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="user_admin")

    assert page["data"] == []


async def test_blank_query_text_is_ignored_rather_than_matching_nothing(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="   ")

    assert _ids(page) == ["evt_0001"]


async def test_query_text_is_trimmed_before_matching(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME, kind="user.role_assigned")
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text="  role_assigned  ")

    assert _ids(page) == ["evt_0001"]


async def test_query_text_longer_than_the_cap_matches_on_its_truncated_prefix(session) -> None:
    prefix = "x" * _MAX_QUERY_TEXT
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME, reason=prefix)
    await session.commit()

    page = await list_log_events(session, ADMIN, query_text=prefix + "never-stored")

    # An unclamped needle would find nothing; the cap makes the overflow inert.
    assert _ids(page) == ["evt_0001"]


async def test_query_text_narrows_within_the_window_and_severity_rather_than_replacing_them(
    session,
) -> None:
    _seed(
        session,
        event_id="evt_0001",
        occurred_at=_BASE_TIME,
        kind="backtest.run_failed",
        severity="error",
    )
    _seed(  # right text + severity, outside the window
        session,
        event_id="evt_0002",
        occurred_at=_BASE_TIME + timedelta(days=1),
        kind="backtest.run_failed",
        severity="error",
    )
    _seed(  # right text + window, wrong severity
        session,
        event_id="evt_0003",
        occurred_at=_BASE_TIME,
        kind="backtest.run_failed",
        severity="info",
    )
    await session.commit()

    page = await list_log_events(
        session,
        ADMIN,
        from_at=_BASE_TIME - timedelta(minutes=1),
        to_at=_BASE_TIME + timedelta(minutes=1),
        severity="error",
        query_text="run_failed",
    )

    assert _ids(page) == ["evt_0001"]


# --------------------------------------------------------------------------- #
# Keyset tie-break on equal occurred_at                                        #
# --------------------------------------------------------------------------- #


async def test_orders_events_sharing_a_timestamp_by_descending_event_id(session) -> None:
    for index in (1, 2, 3):
        _seed(session, event_id=f"evt_{index:04d}", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN)

    assert _ids(page) == ["evt_0003", "evt_0002", "evt_0001"]


async def test_cursor_walk_over_events_sharing_a_timestamp_visits_each_exactly_once(
    session,
) -> None:
    for index in range(1, 6):
        _seed(session, event_id=f"evt_{index:04d}", occurred_at=_BASE_TIME)
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):  # bounded: a non-advancing cursor must fail, not spin
        page = await list_log_events(session, ADMIN, limit=2, cursor=cursor)
        seen.extend(_ids(page))
        cursor = page["meta"]["cursor"]
        if cursor is None:
            break

    assert cursor is None
    assert seen == ["evt_0005", "evt_0004", "evt_0003", "evt_0002", "evt_0001"]


async def test_cursor_crossing_a_tie_boundary_neither_repeats_nor_skips_an_event(session) -> None:
    # Two events share the newer timestamp; the page boundary falls between them, so
    # only the composite (time, id) cursor can resume correctly.
    _seed(session, event_id="evt_0003", occurred_at=_BASE_TIME + timedelta(minutes=1))
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME + timedelta(minutes=1))
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    first = await list_log_events(session, ADMIN, limit=1)
    second = await list_log_events(session, ADMIN, limit=1, cursor=first["meta"]["cursor"])

    assert _ids(first) == ["evt_0003"]
    assert _ids(second) == ["evt_0002"]


# --------------------------------------------------------------------------- #
# Page limit clamping                                                          #
# --------------------------------------------------------------------------- #


async def test_absent_limit_falls_back_to_the_default_page_size(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN)

    assert page["meta"]["limit"] == DEFAULT_LOG_LIMIT


async def test_limit_above_the_maximum_is_clamped_to_the_maximum(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    page = await list_log_events(session, ADMIN, limit=MAX_LOG_LIMIT + 500)

    assert page["meta"]["limit"] == MAX_LOG_LIMIT


async def test_limit_below_one_is_raised_to_a_single_row(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    _seed(session, event_id="evt_0002", occurred_at=_BASE_TIME + timedelta(minutes=1))
    await session.commit()

    page = await list_log_events(session, ADMIN, limit=0)

    assert page["meta"]["limit"] == 1
    assert _ids(page) == ["evt_0002"]
    assert page["meta"]["has_more"] is True


# --------------------------------------------------------------------------- #
# Authorization                                                                #
# --------------------------------------------------------------------------- #


async def test_rejects_a_non_admin_before_any_filter_is_applied(session) -> None:
    _seed(session, event_id="evt_0001", occurred_at=_BASE_TIME)
    await session.commit()

    with pytest.raises(AdminPanelAccessRequiredError):
        await list_log_events(session, USER, from_at=_BASE_TIME, query_text="role")
