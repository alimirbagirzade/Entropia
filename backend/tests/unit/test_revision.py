from entropia.domain.revision import canonical_json, content_hash, next_revision_no


def test_canonical_json_is_key_order_independent() -> None:
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert content_hash(a) == content_hash(b)


def test_content_hash_changes_with_payload() -> None:
    assert content_hash({"x": 1}) != content_hash({"x": 2})


def test_content_hash_is_sha256_hex() -> None:
    h = content_hash({"x": 1})
    assert len(h) == 64
    int(h, 16)  # valid hex


def test_next_revision_no() -> None:
    assert next_revision_no(None) == 1
    assert next_revision_no(1) == 2
    assert next_revision_no(7) == 8
