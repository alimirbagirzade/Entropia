"""O-10: pure package dependency-graph reader + cycle detection (doc 08 §14).

Doc 08 §14 "Dependency cycle" fixes the acceptance: *"Publish attempt creates
A -> B -> A dependency path"* -> *"Server rejects publish; diagnostic identifies
cycle path"*. These tests pin the two pure pieces that make the diagnostic possible:

* ``extract_package_refs`` reads package-to-package claims out of the free-form
  ``dependency_snapshot`` — and must NOT mistake an Embedded System Package
  resolver ref (doc 09, a different registry) for a package edge, or every existing
  Create-Package publish would start failing.
* ``find_dependency_cycle`` returns the CLOSED root-id path, not a boolean.
"""

from __future__ import annotations

from entropia.domain.package.dependency_graph import (
    extract_package_refs,
    find_dependency_cycle,
)

A = "pkg_aaaaaaaa"
B = "pkg_bbbbbbbb"
C = "pkg_cccccccc"
D = "pkg_dddddddd"


# --------------------------------------------------------------------------- #
# find_dependency_cycle                                                        #
# --------------------------------------------------------------------------- #


def test_two_node_cycle_returns_the_closed_path() -> None:
    """The doc 08 §14 acceptance case: A -> B -> A."""
    cycle = find_dependency_cycle(A, {A: (B,), B: (A,)})

    assert cycle == (A, B, A)


def test_three_node_cycle_returns_every_root_on_the_loop() -> None:
    cycle = find_dependency_cycle(A, {A: (B,), B: (C,), C: (A,)})

    assert cycle == (A, B, C, A)


def test_self_reference_is_a_one_element_cycle() -> None:
    """A revision pinning any revision of its OWN root closes the shortest loop."""
    cycle = find_dependency_cycle(A, {A: (A,)})

    assert cycle == (A, A)


def test_acyclic_graph_has_no_cycle() -> None:
    """A diamond (A -> B, A -> C, B -> D, C -> D) re-visits D but never loops."""
    assert find_dependency_cycle(A, {A: (B, C), B: (D,), C: (D,), D: ()}) is None


def test_start_root_with_no_edges_has_no_cycle() -> None:
    assert find_dependency_cycle(A, {}) is None
    assert find_dependency_cycle(A, {B: (A,)}) is None


def test_cycle_not_reachable_from_the_start_root_is_not_reported() -> None:
    """The gate answers for the candidate being published, not the whole catalog."""
    assert find_dependency_cycle(A, {A: (D,), B: (C,), C: (B,), D: ()}) is None


def test_cycle_reported_from_the_root_where_the_loop_closes() -> None:
    """A tail into a loop reports only the looping segment, not the approach path."""
    cycle = find_dependency_cycle(A, {A: (B,), B: (C,), C: (B,)})

    assert cycle == (B, C, B)


def test_first_declared_cycle_wins_so_the_path_is_deterministic() -> None:
    edges = {A: (B, C), B: (A,), C: (A,)}

    assert find_dependency_cycle(A, edges) == (A, B, A)
    assert find_dependency_cycle(A, edges) == (A, B, A)


def test_long_chain_does_not_exhaust_the_recursion_limit() -> None:
    """Detection is an explicit stack, so depth is bounded by rows, not by Python."""
    roots = [f"pkg_{index:05d}" for index in range(5_000)]
    edges = {root: (roots[index + 1],) for index, root in enumerate(roots[:-1])}
    edges[roots[-1]] = (roots[0],)

    assert find_dependency_cycle(roots[0], edges) == (*roots, roots[0])


# --------------------------------------------------------------------------- #
# extract_package_refs                                                         #
# --------------------------------------------------------------------------- #


def test_canonical_package_list_yields_root_and_pinned_revision() -> None:
    refs = extract_package_refs(
        {"packages": [{"package_root_id": B, "package_revision_id": "pkgrev_b1"}]}
    )

    assert len(refs) == 1
    assert refs[0].root_id == B
    assert refs[0].revision_id == "pkgrev_b1"
    assert refs[0].origin == "packages[0]"


def test_embedded_system_resolver_refs_are_not_package_edges() -> None:
    """The Pre-Check scan's ``resolved`` list pins ESP revisions (doc 09) — a
    different registry. Reading them as package edges would break every existing
    Create-Package publish."""
    snapshot = {
        "resolved": [
            {
                "call": "ta.rsi",
                "canonical_key": "ta.rsi",
                "embedded_entity_id": "esp_rsi",
                "embedded_revision_id": "esprev_rsi_1",
                "content_hash": "0" * 64,
            }
        ],
        "scan_id": "scan_1",
    }

    assert extract_package_refs(snapshot) == ()


def test_package_scoped_entry_inside_the_resolved_list_is_still_read() -> None:
    snapshot = {
        "resolved": [
            {"embedded_entity_id": "esp_rsi", "embedded_revision_id": "esprev_rsi_1"},
            {"package_root_id": B, "package_revision_id": "pkgrev_b1"},
        ]
    }
    refs = extract_package_refs(snapshot)

    assert len(refs) == 1
    assert (refs[0].root_id, refs[0].origin) == (B, "resolved[1]")


def test_explicit_indicator_link_at_the_top_level_is_a_package_edge() -> None:
    """doc 06 §4: "the saved dependency is the root and revision identifier"."""
    refs = extract_package_refs(
        {
            "linked_indicator_package_root_id": B,
            "linked_indicator_package_revision_id": "pkgrev_b1",
        }
    )

    assert len(refs) == 1
    assert (refs[0].root_id, refs[0].revision_id) == (B, "pkgrev_b1")
    assert refs[0].origin == "dependency_snapshot"


def test_root_only_and_revision_only_claims_are_both_kept() -> None:
    refs = extract_package_refs(
        {"packages": [{"package_root_id": B}, {"package_revision_id": "pkgrev_c1"}]}
    )

    assert [(ref.root_id, ref.revision_id) for ref in refs] == [
        (B, None),
        (None, "pkgrev_c1"),
    ]


def test_claims_are_returned_in_declaration_order() -> None:
    refs = extract_package_refs(
        {"packages": [{"package_root_id": B}, {"package_root_id": C}, {"package_root_id": D}]}
    )

    assert [ref.root_id for ref in refs] == [B, C, D]


def test_unreadable_snapshots_declare_no_package_dependency() -> None:
    for snapshot in (None, {}, [], "pkg_aaaaaaaa", 7, {"resolved": "not-a-list"}):
        assert extract_package_refs(snapshot) == ()


def test_blank_and_non_string_identifiers_are_ignored() -> None:
    snapshot = {
        "packages": [
            {"package_root_id": "   ", "package_revision_id": None},
            {"package_root_id": 42},
            {"package_root_id": B},
        ]
    }
    refs = extract_package_refs(snapshot)

    assert [ref.root_id for ref in refs] == [B]
