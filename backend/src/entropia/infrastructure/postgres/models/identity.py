"""Identity tables: principals, human users, the system Agent (M1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column


class Principal(TimestampMixin, Base):
    """Every actor identity (human, agent, system) has a principal row."""

    __tablename__ = "principals"

    principal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    principal_type: Mapped[PrincipalType] = mapped_column(
        enum_column(PrincipalType, "principal_type"), nullable=False
    )


class HumanUser(TimestampMixin, Base):
    """The only mutable user root. Fixed, title-based role."""

    __tablename__ = "human_users"

    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("principals.principal_id"), primary_key=True
    )
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    current_role: Mapped[Role] = mapped_column(enum_column(Role, "role"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    role_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role_changed_by: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Deletion overlay (orthogonal to role/status).
    deletion_state: Mapped[DeletionState] = mapped_column(
        enum_column(DeletionState, "deletion_state"), nullable=False, default=DeletionState.ACTIVE
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class Agent(TimestampMixin, Base):
    """Non-login system Agent actor. Not in the human user registry."""

    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("principals.principal_id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
