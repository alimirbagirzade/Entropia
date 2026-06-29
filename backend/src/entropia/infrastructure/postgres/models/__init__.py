"""All ORM models. Importing this package registers every table on
``Base.metadata`` (used by Alembic autogenerate and create_all in tests)."""

from entropia.infrastructure.postgres.models.audit import AuditEvent, OutboxEvent
from entropia.infrastructure.postgres.models.deletion import Tombstone, TrashEntry
from entropia.infrastructure.postgres.models.identity import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.models.jobs import IdempotencyKey, Job
from entropia.infrastructure.postgres.models.registry import EntityRegistry, EntityRevision
from entropia.infrastructure.postgres.models.system import AppMetadata

__all__ = [
    "Agent",
    "AppMetadata",
    "AuditEvent",
    "EntityRegistry",
    "EntityRevision",
    "HumanUser",
    "IdempotencyKey",
    "Job",
    "OutboxEvent",
    "Principal",
    "Tombstone",
    "TrashEntry",
]
