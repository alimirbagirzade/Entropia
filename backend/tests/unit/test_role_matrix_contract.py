"""Exhaustive lock on the canonical Role Scope Matrix projection (doc 19 §3.3, §4.1, §6.1).

The matrix is server truth rendered read-only by the Management screen: the client
never computes it and never edits it. A silent edit to one cell would therefore
change what the product *claims* a role may do, with no failing assertion anywhere
— ``test_admin_panel_taxonomy.py::test_role_matrix_projection`` pins only the row
set, the revision and four spot cells, leaving most of the 4x5 grid unguarded.

These tests lock the WHOLE grid — every role against every capability column — plus
the projection's structural promises (stable row order, complete columns, per-call
copy). Behaviour is unchanged; this only makes a regression loud.
"""

from __future__ import annotations

import pytest

from entropia.domain.admin_panel.role_matrix import ROLE_MATRIX_REVISION, build_role_matrix

# The canonical grid, transcribed from DOMAIN_MODEL §4/§5 policy. Kept as a literal
# table (not derived from the module under test) so a change to the shipped policy
# has to be made deliberately in two places.
_CANONICAL_ROWS: dict[str, dict[str, object]] = {
    "admin": {
        "is_system_actor": False,
        "assignable": True,
        "view_use": "all",
        "edit": "all",
        "delete": "all",
        "trash": "manage",
        "role_assignment": "manage",
    },
    "supervisor": {
        "is_system_actor": False,
        "assignable": True,
        "view_use": "shared_and_published",
        "edit": "own",
        "delete": "own",
        "trash": "none",
        "role_assignment": "none",
    },
    "user": {
        "is_system_actor": False,
        "assignable": True,
        "view_use": "own_and_published",
        "edit": "own",
        "delete": "own",
        "trash": "none",
        "role_assignment": "none",
    },
    "agent": {
        "is_system_actor": True,
        "assignable": False,
        "view_use": "own_system_outputs",
        "edit": "own_output",
        "delete": "none",
        "trash": "none",
        "role_assignment": "none",
    },
}

_CAPABILITY_COLUMNS = ("view_use", "edit", "delete", "trash", "role_assignment")

_ALL_CELLS = [
    (role, column, values[column])
    for role, values in _CANONICAL_ROWS.items()
    for column in _CAPABILITY_COLUMNS
]


def _rows_by_role() -> dict[str, dict[str, object]]:
    return {str(row["role"]): row for row in build_role_matrix()["rows"]}


def test_matrix_lists_the_four_canonical_rows_in_a_stable_order() -> None:
    # Order is presentation contract: the screen renders rows top-to-bottom as given.
    assert [row["role"] for row in build_role_matrix()["rows"]] == [
        "admin",
        "supervisor",
        "user",
        "agent",
    ]


@pytest.mark.parametrize(("role", "column", "expected"), _ALL_CELLS)
def test_every_role_capability_cell_matches_the_canonical_policy(
    role: str, column: str, expected: object
) -> None:
    assert _rows_by_role()[role][column] == expected


@pytest.mark.parametrize("role", sorted(_CANONICAL_ROWS))
def test_every_row_declares_every_advertised_column(role: str) -> None:
    row = _rows_by_role()[role]
    assert set(row) == {"role", "is_system_actor", "assignable", *_CAPABILITY_COLUMNS}


def test_advertised_columns_are_exactly_the_capability_columns() -> None:
    # The client renders one column per entry; an unrendered key would be invisible
    # policy, and an advertised-but-absent key would render as a hole.
    assert build_role_matrix()["columns"] == list(_CAPABILITY_COLUMNS)


def test_policy_revision_is_published_with_the_matrix() -> None:
    matrix = build_role_matrix()
    assert matrix["policy_revision"] == ROLE_MATRIX_REVISION
    assert ROLE_MATRIX_REVISION == "2026-06-role-matrix-v1"


def test_agent_is_the_only_system_actor_and_is_never_assignable() -> None:
    rows = _rows_by_role()
    assert [role for role, row in rows.items() if row["is_system_actor"]] == ["agent"]
    assert [role for role, row in rows.items() if not row["assignable"]] == ["agent"]


def test_only_admin_may_manage_trash_and_role_assignment() -> None:
    rows = _rows_by_role()
    assert [role for role, row in rows.items() if row["trash"] != "none"] == ["admin"]
    assert [role for role, row in rows.items() if row["role_assignment"] != "none"] == ["admin"]


def test_returns_a_fresh_copy_so_a_caller_cannot_mutate_the_canonical_policy() -> None:
    first = build_role_matrix()
    first["rows"][0]["delete"] = "none"
    first["columns"].append("injected")

    second = build_role_matrix()
    assert second["rows"][0]["delete"] == "all"
    assert "injected" not in second["columns"]
