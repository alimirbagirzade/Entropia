"""G14 / GH #544 decision B: NET is no longer a selectable cross-item conflict policy

``NET`` (offsetting the aggregate position) has no canonical definition. Neither doc 13
nor Master Ref Modül 11 §6.3 states a netting price, position custody, fee attribution,
realized-PnL attribution or margin treatment for an offset pair, so the two engines
disagreed about the value: the sequential engine downgraded it to BLOCK_OPPOSITE while
the unified-clock phase loop refused it outright. Decision ``B`` (signed 2026-08-26,
``docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md``) ends that contradiction
at the root by dropping the value.

WHAT THIS MIGRATION ACTUALLY DOES, AND WHY IT IS NOT WHAT §Ölçüm 4 EXPECTED.
That measurement framed ``B`` as *rewriting* a CHECK constraint, on the reading that
``enum_column`` produces "VARCHAR + CHECK". Measured against the shipped database: it does
NOT. ``SAEnum(..., native_enum=False)`` leaves ``create_constraint`` at its SQLAlchemy 2.0
default of **False**, so ``portfolio_allocation_plan.conflict_policy`` is a plain
``character varying`` with no constraint at all — ``validate_strings=True`` only guards the
PYTHON side. There was therefore no CHECK to rewrite, and the column has never enforced the
enum: a direct SQL write could store any string. This migration ADDS the constraint that
measurement assumed already existed, narrowed to the two surviving values, so Decision 1's
promise that the value "can no longer be recorded ... at the root" is true of the COLUMN
and not merely of the ORM.

B3 (Decision 2, signed 2026-08-27) — THE HALT IS THE POINT, NOT AN ERROR PATH.
Rows carrying ``'NET'`` are neither rewritten to BLOCK_OPPOSITE (``B1``) nor nulled
(``B2``): both were rejected as silent changes to a configuration the user chose. This
migration HALTS instead and leaves the decision to the operator. The write path was frozen
first (``B0``, shipped in #858) precisely so the set could drain before this ran; that
ordering is part of the signature, which is why the two ship in separate releases.

The second guard is NOT in the signature and is a consequence of the finding above: because
the column was never constrained, a value outside the enum may exist. A bare ADD CONSTRAINT
would fail on it with an opaque Postgres error naming neither the column nor the rows, so
the drift is counted first and reported honestly — the same fail-closed reading, one class
wider.

``portfolio_allocation_plan`` holds one row per composition, so the constraint is added and
validated in one statement rather than the NOT VALID / VALIDATE two-step that a large table
would need.

Revision ID: 0044_drop_net_conflict_policy
Revises: 0043_i08_registry_strategy_fks
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_drop_net_conflict_policy"
down_revision: str | None = "0043_i08_registry_strategy_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "portfolio_allocation_plan"
_COLUMN = "conflict_policy"
_CONSTRAINT = "ck_portfolio_allocation_plan_conflict_policy"

# The values that survive decision B. Spelled out rather than imported from
# ``CrossItemConflictPolicy``: 0035 imported the live enum and that is exactly why this
# file exists as a schema change at all — a migration that reads today's domain code does
# not describe the database it actually built. A migration is a historical record.
_ALLOWED = ("BLOCK_OPPOSITE", "KEEP_SEPARATE")
_REMOVED = "NET"
_PRE_B_ALLOWED = (_REMOVED, *_ALLOWED)

_DECISION = "docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md"


def _check(values: Sequence[str]) -> str:
    """``NULL`` stays legal: it is the absence of a cross-item rule (KEEP_SEPARATE by
    definition, doc 13 §8.4), not an unset-and-invalid value. 0035 created the column
    nullable with no backfill and this migration does not change that."""
    listed = ", ".join(f"'{v}'" for v in values)
    return f"{_COLUMN} IS NULL OR {_COLUMN} IN ({listed})"


def _halt(count: int, *, values: str, why: str, remedy: str) -> None:
    raise RuntimeError(
        f"Migration {revision} HALTED: {count} row(s) in {_TABLE} carry {values}. {why} "
        f"{remedy} Then re-run the migration. This halt is decision B3 "
        f"({_DECISION}, GH #544): such a row is deliberately NOT rewritten and NOT nulled, "
        "because either would silently change a configuration the operator chose."
    )


def upgrade() -> None:
    bind = op.get_bind()

    # B3 first, and named separately from the drift guard below: an operator who sees this
    # message is being asked a product question ("which policy did you actually want?"),
    # not told about corrupt data.
    net_rows = bind.scalar(
        sa.text(f"SELECT count(*) FROM {_TABLE} WHERE {_COLUMN} = :v"), {"v": _REMOVED}
    )
    if net_rows:
        _halt(
            int(net_rows),
            values=f"conflict_policy = '{_REMOVED}'",
            why=(
                "NET has no canonical definition, so no automatic replacement can be "
                "honest about what the plan meant."
            ),
            remedy=(
                "Open each affected composition's allocation plan and choose BLOCK_OPPOSITE "
                "(a later-pinned item's opposing same-instrument entry is blocked) or "
                "KEEP_SEPARATE (items replay independently)."
            ),
        )

    # Not in the signature — see the module docstring. The column was never constrained, so
    # a value outside the enum can exist and ADD CONSTRAINT would fail opaquely on it.
    drift_rows = bind.scalar(
        sa.text(
            f"SELECT count(*) FROM {_TABLE} "
            f"WHERE {_COLUMN} IS NOT NULL AND {_COLUMN} <> ALL(:allowed)"
        ),
        {"allowed": list(_PRE_B_ALLOWED)},
    )
    if drift_rows:
        _halt(
            int(drift_rows),
            values="a conflict_policy outside the shipped enum",
            why=(
                "The column has never carried a CHECK constraint, so such a value was "
                "writable; this migration is what starts enforcing the set."
            ),
            remedy=(
                "Inspect them with: SELECT id, conflict_policy FROM "
                f"{_TABLE} WHERE {_COLUMN} IS NOT NULL AND {_COLUMN} NOT IN "
                f"({', '.join(repr(v) for v in _PRE_B_ALLOWED)}); and set each to "
                "BLOCK_OPPOSITE, KEEP_SEPARATE or NULL."
            ),
        )

    op.create_check_constraint(_CONSTRAINT, _TABLE, _check(_ALLOWED))


def downgrade() -> None:
    """Back to the shipped state EXACTLY: no constraint on the column.

    Not a constraint that re-admits NET — there was none before this migration, and
    creating one on the way down would leave the database in a state no upgrade path ever
    produced. Rows are untouched in both directions (there are none to touch: upgrade
    refuses to run while a NET row exists)."""
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
