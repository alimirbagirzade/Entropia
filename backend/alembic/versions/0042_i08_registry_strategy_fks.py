"""I-08 slice 1 — put the registry-owner and strategy head/family edges under the DB

Three cross-reference columns carried a real reference but only an application-level
promise that the target existed (I-08). A bug, a partial rollback or a hand-written
UPDATE could leave a strategy pointing at a revision that was never written, and
nothing would notice until a reader 500'd. This migration hands the promise to
Postgres:

* ``entity_registry.owner_principal_id`` -> ``principals.principal_id``
* ``strategy_root.current_revision_id``  -> ``strategy_revision.revision_id``
* ``strategy_root.rationale_family_id``  -> ``rationale_family_root.entity_id``

ON DELETE is NO ACTION (the SQL default) for all three, deliberately:

* V1 never hard-DELETEs any of these rows — ``jobs/purge.py`` is state-only
  ("root row and immutable revisions are RETAINED as identity/audit evidence"), so
  the realistic event a constraint has to survive is a BUG, and blocking is the
  honest response. SET NULL would silently erase a live head pointer or an entity's
  owner; CASCADE would delete a whole strategy because one revision row went away.
* NO ACTION rather than the stricter RESTRICT because ``strategy_root.entity_id``
  and ``strategy_revision.entity_id`` both cascade from ``entity_registry``: a
  registry-level cascade deletes root and revisions in ONE statement, and only
  NO ACTION lets the check wait for the end of that statement. RESTRICT would fire
  mid-cascade and break a delete path that is otherwise legal.

Two columns named in the I-08 report are deliberately NOT constrained, here or in a
later slice, because they are POLYMORPHIC and no single target table exists:
``entity_registry.current_revision_id`` (each domain repo advances it into its own
revision table — see the model comment) and
``package_rationale_assignment.target_revision_id`` (doc 10 §9.1 declares two target
kinds). Naming them here is the documentation the report asked for, not an omission.

Constraint names match what ``Base.metadata.create_all`` produces (Postgres default
``<table>_<column>_fkey``), so the alembic-built schema and the test-built schema are
byte-identical. Downgrade drops the three constraints and restores the loose columns.

Revision ID: 0042_i08_registry_strategy_fks
Revises: 0041_filtered_event_artifact
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0042_i08_registry_strategy_fks"
down_revision: str | None = "0041_filtered_event_artifact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWNER_FK = "entity_registry_owner_principal_id_fkey"
_HEAD_FK = "strategy_root_current_revision_id_fkey"
_FAMILY_FK = "strategy_root_rationale_family_id_fkey"


def upgrade() -> None:
    op.create_foreign_key(
        _OWNER_FK,
        "entity_registry",
        "principals",
        ["owner_principal_id"],
        ["principal_id"],
    )
    op.create_foreign_key(
        _HEAD_FK,
        "strategy_root",
        "strategy_revision",
        ["current_revision_id"],
        ["revision_id"],
    )
    op.create_foreign_key(
        _FAMILY_FK,
        "strategy_root",
        "rationale_family_root",
        ["rationale_family_id"],
        ["entity_id"],
    )


def downgrade() -> None:
    op.drop_constraint(_FAMILY_FK, "strategy_root", type_="foreignkey")
    op.drop_constraint(_HEAD_FK, "strategy_root", type_="foreignkey")
    op.drop_constraint(_OWNER_FK, "entity_registry", type_="foreignkey")
