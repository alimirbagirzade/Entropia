"""Local-auth tables: human credentials and opaque auth sessions (M1 §4).

Credentials live apart from ``human_users`` so the user root never carries
secret material. Sessions store only a SHA-256 digest of the opaque Bearer
token — the raw token is returned once at login and never persisted.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin


class HumanCredential(TimestampMixin, Base):
    """One password credential per human user (argon2id hash, never the secret)."""

    __tablename__ = "human_credentials"

    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("human_users.user_id"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="argon2id")


class AuthSession(TimestampMixin, Base):
    """Server-side revocable session; the authority for Bearer-token requests."""

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("idx_auth_sessions_user_id", "user_id"),)

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("human_users.user_id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReauthProof(TimestampMixin, Base):
    """A short-lived, single-use proof that the active human re-entered their
    password for a specific sensitive action (F-21, doc 20 §8.3).

    Mirrors ``AuthSession``: only a SHA-256 digest of the opaque proof token is
    stored, never the raw value (returned once from ``POST /auth/reauth``).
    ``purpose`` scopes the proof to the action it was issued for (e.g.
    ``trash_purge``) so a proof minted for one sensitive action can't silently
    authorize a different one. ``used_at`` enforces single-use — consuming a
    proof stamps it in the SAME transaction as the action it authorizes, so a
    replayed token is rejected deterministically (no race window).
    """

    __tablename__ = "reauth_proofs"
    __table_args__ = (Index("idx_reauth_proofs_user_id", "user_id"),)

    proof_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("human_users.user_id"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
