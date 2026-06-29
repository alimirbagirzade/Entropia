"""Declarative base for all ORM models (domain tables arrive in Stage 1+)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base. One metadata for the whole app."""
