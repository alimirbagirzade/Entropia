"""F-07 §4.4 — the four display-DTO labels, against a real database.

F-07's prescribed correction is *"Add display DTOs at query boundaries; never
reconstruct names from IDs in the browser"*. Two of the four surfaces read PINNED,
immutable artifacts (a readiness report, a backtest result), so the label has to be
captured where the artifact is WRITTEN — labelling a finished artifact from the live
composition would attach names it never saw.

These tests pin the two properties that are easy to regress:

* the label a report serves comes from the snapshot the report pinned, so RENAMING the
  composition item afterwards does NOT rewrite the report's labels;
* an object with no name yields NULL, never a name derived from its id.

Auto-skips when no PostgreSQL is reachable (tests/integration/conftest.py).
"""

from __future__ import annotations

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import package_import as import_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import package_import as import_query
from entropia.application.queries import readiness_check as readiness_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    MainboardCompositionSnapshot,
    MainboardWorkingItem,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo

# Reuse the Stage-4b seeding helpers rather than re-deriving a valid strategy payload
# (market revision + approved indicator package + config) a second time.
from tests.integration.test_readiness_persistence import (
    _composition_with_strategy,
    _seed_principals,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_LABEL = "Momentum A"
_RENAMED = "Renamed After The Report"


async def _labelled_composition(session) -> tuple[str, str]:
    """A composition holding the SAME strategy twice — the second copy labelled.

    The duplicate is what makes this test deterministic: a valid single-Strategy
    composition is simply READY and produces no item-scoped finding, while
    ``DUPLICATE_ENABLED_ITEM`` always carries ``scope_id`` = the SECOND occurrence's
    item id (``domain.readiness.validators``). Labelling only that second copy means
    the assertions cannot pass by accident from the other row, and the first copy
    doubles as the unlabelled -> NULL case.

    Returns ``(composition_id, labelled_item_id)``.
    """
    composition_id = await _composition_with_strategy(session, USER1)
    first = await _sole_item(session, composition_id)
    duplicate = await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=composition_id,
        root_id=first.work_object_root_id,
        revision_id=first.pinned_revision_id,
        item_kind="strategy",
    )
    await mb_cmd.patch_mainboard_item(
        session,
        USER1,
        item_id=duplicate["item_id"],
        intent="set_label",
        expected_row_version=duplicate["row_version"],
        display_label_override=_LABEL,
    )
    await session.commit()
    return composition_id, duplicate["item_id"]


async def _sole_item(session, composition_id: str) -> MainboardWorkingItem:
    items = await mb_repo.list_active_items(session, composition_id)
    assert len(items) == 1, f"expected exactly one composition item, got {len(items)}"
    return items[0]


async def _item(session, item_id: str) -> MainboardWorkingItem:
    item = await mb_repo.get_item(session, item_id)
    assert item is not None
    return item


# --------------------------------------------------------------------------- #
# Surface 4 — Ready Check issue scope                                          #
# --------------------------------------------------------------------------- #


async def test_snapshot_manifest_pins_the_item_label(session) -> None:
    """The label must be captured INTO the snapshot, not looked up at read time."""
    await _seed_principals(session)
    composition_id, labelled_item_id = await _labelled_composition(session)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    snapshot = await session.get(MainboardCompositionSnapshot, result["snapshot_id"])
    assert snapshot is not None
    labels = {i["item_id"]: i.get("label") for i in snapshot.item_manifest["items"]}
    assert labels[labelled_item_id] == _LABEL
    # The unlabelled twin pins None — never a name derived from its id.
    assert set(labels.values()) == {_LABEL, None}


async def test_readiness_issue_carries_the_scope_label(session) -> None:
    await _seed_principals(session)
    composition_id, labelled_item_id = await _labelled_composition(session)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    scoped = [i for i in result["issues"] if i.get("scope_id") == labelled_item_id]
    assert scoped, "expected an item-scoped issue for the labelled duplicate"
    assert all(i["scope_label"] == _LABEL for i in scoped)

    # The read model must agree with the POST body it just returned.
    report = await readiness_query.get_readiness_report(
        session, USER1, report_id=result["report_id"]
    )
    read_scoped = [i for i in report["issues"] if i["scope_id"] == labelled_item_id]
    assert read_scoped and all(i["scope_label"] == _LABEL for i in read_scoped)


async def test_renaming_the_item_does_not_relabel_an_existing_report(session) -> None:
    """THE invariant this design exists for.

    A report is immutable and ``is_current``-tracked. If its labels were joined from
    the live composition, renaming an item would silently rewrite the history of every
    past report — showing a name that report never validated against.
    """
    await _seed_principals(session)
    composition_id, labelled_item_id = await _labelled_composition(session)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    item = await _item(session, labelled_item_id)
    await mb_cmd.patch_mainboard_item(
        session,
        USER1,
        item_id=labelled_item_id,
        intent="set_label",
        expected_row_version=item.row_version,
        display_label_override=_RENAMED,
    )
    await session.commit()

    report = await readiness_query.get_readiness_report(
        session, USER1, report_id=result["report_id"]
    )
    scoped = [i for i in report["issues"] if i["scope_id"] == labelled_item_id]
    assert scoped
    assert all(i["scope_label"] == _LABEL for i in scoped), "report was relabelled from live data"
    assert all(i["scope_label"] != _RENAMED for i in scoped)


async def test_unlabelled_scope_reports_null_not_a_derived_name(session) -> None:
    await _seed_principals(session)
    composition_id, labelled_item_id = await _labelled_composition(session)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    report = await readiness_query.get_readiness_report(
        session, USER1, report_id=result["report_id"]
    )
    others = [
        i
        for i in report["issues"]
        if i["scope_id"] is not None and i["scope_id"] != labelled_item_id
    ]
    # Whatever else was flagged, an unlabelled item must never invent a name.
    assert all(i["scope_label"] is None for i in others)


# --------------------------------------------------------------------------- #
# Surface 2 — Library import job                                               #
# --------------------------------------------------------------------------- #


async def test_import_job_pins_the_submitted_package_name(session) -> None:
    await _seed_principals(session)

    submitted = await import_cmd.submit_package_import(
        session,
        USER1,
        manifest={
            "package_kind": "indicator",
            "package_root_id": "pkg_origin",
            "revision_id": "pkgrev_origin",
            "name": "Momentum Reversal v3",
        },
    )
    await session.commit()

    report = await import_query.get_import_report(
        session, USER1, import_job_id=submitted["import_job_id"]
    )
    assert report["source_package_name"] == "Momentum Reversal v3"


async def test_import_job_without_a_manifest_name_reports_null(session) -> None:
    """A manifest that declares no name must NOT get one invented from its hash/id."""
    await _seed_principals(session)

    submitted = await import_cmd.submit_package_import(
        session,
        USER1,
        manifest={"package_kind": "indicator", "package_root_id": "pkg_origin_2"},
    )
    await session.commit()

    report = await import_query.get_import_report(
        session, USER1, import_job_id=submitted["import_job_id"]
    )
    assert report["source_package_name"] is None
