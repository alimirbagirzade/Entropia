"""Unit: password hashing seam + Bearer parsing (no infra)."""

from __future__ import annotations

from starlette.requests import Request

from entropia.application.commands.auth import hash_token
from entropia.apps.api.deps import bearer_token
from entropia.shared.passwords import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    verify_password,
)


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_password_hash_roundtrip() -> None:
    digest = hash_password("a-strong-enough-pass")
    assert digest != "a-strong-enough-pass"
    assert verify_password(digest, "a-strong-enough-pass")
    assert not verify_password(digest, "a-wrong-pass")
    assert not needs_rehash(digest)


def test_verify_tolerates_garbage_hash() -> None:
    assert not verify_password("not-a-real-hash", "anything")
    assert not verify_password(DUMMY_HASH, "anything")


def test_hash_token_is_stable_sha256_hex() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert len(hash_token("abc")) == 64
    assert hash_token("abc") != hash_token("abd")


def test_bearer_token_parsing() -> None:
    assert bearer_token(_request({"Authorization": "Bearer tok-123"})) == "tok-123"
    assert bearer_token(_request({"Authorization": "bearer tok-123"})) == "tok-123"
    assert bearer_token(_request({})) is None
    assert bearer_token(_request({"Authorization": "Basic dXNlcg=="})) is None
    assert bearer_token(_request({"Authorization": "Bearer   "})) is None
