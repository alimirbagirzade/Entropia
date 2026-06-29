from entropia.shared.idempotency import request_fingerprint


def test_same_payload_same_fingerprint() -> None:
    assert request_fingerprint({"a": 1, "b": 2}) == request_fingerprint({"b": 2, "a": 1})


def test_different_payload_different_fingerprint() -> None:
    assert request_fingerprint({"a": 1}) != request_fingerprint({"a": 2})
