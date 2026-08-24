"""RC-17.c2 — the Ready Check denial envelope carries no composition detail.

Doc 14 §15 RC-17 asks for two things from an unauthorized check on a private
composition: a 403, and *no confidential dependency details in response*. The
403 half is already pinned three times over (``test_readiness_persistence.py::
test_rc17_foreign_owner_denied`` plus the two durable-audit cases), all of them
at the command boundary where the response body does not exist yet. The leak
half is only observable on the WIRE, so this case drives the real route through
the ASGI app against a real composition.

The shape is the one ``contract/test_mainboard_contract.py::
test_guest_default_mainboard_does_not_leak_workspace_or_composition`` established
for the Mainboard projection; it had never been applied to the readiness surface.

Two things make the assertion non-vacuous:

* the composition genuinely HAS confidential detail to leak — a strategy item
  pinned to a work object revision, an approved indicator package, a market
  dataset, and a duplicate item that makes the check produce an item-scoped
  blocker;
* the same route, called by the owner over the SAME composition, is asserted to
  emit three of those identifiers verbatim. Without that positive control
  "the 403 does not contain X" would also hold for an X this endpoint can never
  emit at all.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.application.commands import mainboard as mb_cmd
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo

from .test_readiness_persistence import (
    USER1,
    USER2,
    _composition_with_strategy,
    _seed_principals,
    _strategy_payload,
)

pytestmark = pytest.mark.integration

_CHECKS = "/api/v1/mainboard-compositions/{composition_id}/readiness-checks"


def _override(app: Any, session: Any, actor: Actor) -> Iterator[None]:
    """Bind the real session + a chosen actor to the route (library-route style)."""
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=actor)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_rc17_foreign_denial_body_carries_no_composition_or_dependency_detail(
    app, session
) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    item = (await mb_repo.list_active_items(session, composition_id))[0]
    # A second, duplicate attachment so the owner's own check reports an
    # item-SCOPED blocker: that is what puts a Mainboard item id into a readiness
    # response body at all, and therefore what makes its absence measurable.
    duplicate = await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=composition_id,
        root_id=item.work_object_root_id,
        revision_id=item.pinned_revision_id,
        item_kind="strategy",
    )
    await session.commit()

    package_revision_id = _strategy_payload()["position_entry_logic"]["indicator_blocks"][0][
        "package_ref"
    ]["package_revision_id"]
    revision = await mb_repo.get_work_object_revision(session, item.pinned_revision_id)
    assert revision is not None
    market_revision_id = revision.payload["data"]["market_dataset_revision_id"]
    # Everything the composition is made of. ``composition_id`` is deliberately NOT
    # in this set: the caller supplied it in the URL, so echoing it discloses nothing.
    secrets = {
        "item_id": item.item_id,
        "duplicate_item_id": duplicate["item_id"],
        "work_object_root_id": item.work_object_root_id,
        "pinned_revision_id": item.pinned_revision_id,
        "composition_hash": duplicate["composition_hash"],
        "market_dataset_root_id": "md_root_1",
        "market_dataset_revision_id": market_revision_id,
        "indicator_package_revision_id": package_revision_id,
    }

    gen = _override(app, session, USER2)
    next(gen)
    try:
        async with _client(app) as c:
            denied = await c.post(_CHECKS.format(composition_id=composition_id))
    finally:
        next(gen, None)

    assert denied.status_code == 403
    body = denied.json()
    # The whole envelope, and nothing but the envelope.
    assert set(body.keys()) == {"error"}
    assert body["error"]["code"] == "ACCESS_DENIED"
    # ``details`` is doc 01 §11.2's field-issue list (O-02) and the one field on the
    # canonical envelope that could legitimately carry per-object rows — so a denial
    # leaking through it would look structurally valid. It must be empty here.
    assert body["error"]["details"] == []
    assert body["error"]["scope_id"] is None
    # Substring, not key lookup: a leak nested anywhere in the serialized envelope
    # (a message, a remediation string, a details row) is still a leak.
    leaked = {name: value for name, value in secrets.items() if value in denied.text}
    assert leaked == {}

    # Positive control: the very same route emits three of those identifiers to the
    # owner of the very same composition, so their absence above is an observation
    # about the DENIAL and not about the endpoint's vocabulary.
    gen = _override(app, session, USER1)
    next(gen)
    try:
        async with _client(app) as c:
            allowed = await c.post(_CHECKS.format(composition_id=composition_id))
        await session.commit()
    finally:
        next(gen, None)

    assert allowed.status_code == 201
    assert secrets["composition_hash"] in allowed.text
    assert secrets["duplicate_item_id"] in allowed.text
    assert allowed.json()["snapshot_id"] in allowed.text
