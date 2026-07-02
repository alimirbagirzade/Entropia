"""Argon2id password hashing (M1 §4 / Master §20 local-auth decision).

A thin seam over ``argon2-cffi`` so commands never touch the library directly.
``DUMMY_HASH`` lets the login path run one verification even when the username
does not exist, keeping the timing profile of both failure modes aligned
(user-enumeration hardening).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

PASSWORD_ALGORITHM = "argon2id"
MIN_PASSWORD_LENGTH = 10

_hasher = PasswordHasher()

# A valid hash of an unguessable throwaway value, computed once per process.
DUMMY_HASH = _hasher.hash("entropia-dummy-credential-timing-pad")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _hasher.verify(password_hash, candidate)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when stored parameters lag the current policy (rehash on next login)."""
    return _hasher.check_needs_rehash(password_hash)


__all__ = [
    "DUMMY_HASH",
    "MIN_PASSWORD_LENGTH",
    "PASSWORD_ALGORITHM",
    "hash_password",
    "needs_rehash",
    "verify_password",
]
