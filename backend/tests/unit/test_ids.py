from entropia.shared.ids import new_id


def test_new_id_has_prefix_and_is_sortable() -> None:
    a = new_id("run")
    b = new_id("run")
    assert a.startswith("run_")
    assert b.startswith("run_")
    assert a != b
    # ULID-like ids are lexicographically time-ordered.
    assert a <= b or b <= a
