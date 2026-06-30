"""All ORM models. Importing this package registers every table on
``Base.metadata`` (used by Alembic autogenerate and create_all in tests)."""

from entropia.infrastructure.postgres.models.approvals import ApprovalDecision
from entropia.infrastructure.postgres.models.audit import AuditEvent, OutboxEvent
from entropia.infrastructure.postgres.models.create_package import DependencyScan, PackageRequest
from entropia.infrastructure.postgres.models.deletion import Tombstone, TrashEntry
from entropia.infrastructure.postgres.models.esp import (
    EmbeddedResolverContract,
    EmbeddedResolverRegistry,
)
from entropia.infrastructure.postgres.models.identity import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.models.jobs import IdempotencyKey, Job
from entropia.infrastructure.postgres.models.market_data import (
    DatasetCoverageSlice,
    MarketDatasetRevision,
    MarketProcessedAsset,
    MarketRawAsset,
    MarketSchemaMapping,
    MarketValidationIssue,
    MarketValidationRun,
)
from entropia.infrastructure.postgres.models.packages import PackageRevision, PackageRoot
from entropia.infrastructure.postgres.models.rationale import (
    PackageRationaleAssignment,
    RationaleFamilyRevision,
    RationaleFamilyRoot,
)
from entropia.infrastructure.postgres.models.registry import EntityRegistry, EntityRevision
from entropia.infrastructure.postgres.models.research_data import (
    ResearchDatasetRevision,
    ResearchFeatureDefinition,
    ResearchFieldDefinition,
    ResearchMarketLink,
    ResearchNativeAsset,
    ResearchRawAsset,
    ResearchTimePolicy,
    ResearchValidationIssue,
    ResearchValidationRun,
)
from entropia.infrastructure.postgres.models.system import AppMetadata

__all__ = [
    "Agent",
    "AppMetadata",
    "ApprovalDecision",
    "AuditEvent",
    "DatasetCoverageSlice",
    "DependencyScan",
    "EmbeddedResolverContract",
    "EmbeddedResolverRegistry",
    "EntityRegistry",
    "EntityRevision",
    "HumanUser",
    "IdempotencyKey",
    "Job",
    "MarketDatasetRevision",
    "MarketProcessedAsset",
    "MarketRawAsset",
    "MarketSchemaMapping",
    "MarketValidationIssue",
    "MarketValidationRun",
    "OutboxEvent",
    "PackageRationaleAssignment",
    "PackageRequest",
    "PackageRevision",
    "PackageRoot",
    "Principal",
    "RationaleFamilyRevision",
    "RationaleFamilyRoot",
    "ResearchDatasetRevision",
    "ResearchFeatureDefinition",
    "ResearchFieldDefinition",
    "ResearchMarketLink",
    "ResearchNativeAsset",
    "ResearchRawAsset",
    "ResearchTimePolicy",
    "ResearchValidationIssue",
    "ResearchValidationRun",
    "Tombstone",
    "TrashEntry",
]
