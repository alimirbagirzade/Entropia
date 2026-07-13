"""All ORM models. Importing this package registers every table on
``Base.metadata`` (used by Alembic autogenerate and create_all in tests)."""

from entropia.infrastructure.postgres.models.agent_lab import (
    AgentCheckpoint,
    AgentEvent,
    AgentRuntime,
    AgentTask,
    ArtifactLink,
    HypothesisArtifact,
    LabMessage,
    TaskDirective,
)
from entropia.infrastructure.postgres.models.agent_tool_gateway import AgentToolCall
from entropia.infrastructure.postgres.models.allocation import (
    PortfolioAllocationEntry,
    PortfolioAllocationPlan,
    PortfolioAllocationPlanRevision,
)
from entropia.infrastructure.postgres.models.approvals import ApprovalDecision
from entropia.infrastructure.postgres.models.audit import AuditEvent, OutboxEvent
from entropia.infrastructure.postgres.models.auth import AuthSession, HumanCredential
from entropia.infrastructure.postgres.models.backtest import (
    BacktestResult,
    BacktestRun,
    BacktestRunManifest,
    DiagnosticArtifact,
    MetricValueRow,
    ResultEquityPoint,
    ResultManifestSnapshot,
    ResultSummary,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.infrastructure.postgres.models.capability import (
    AnalysisArtifact,
    CapabilityActivationEvent,
    ExecutionPlan,
    ExperimentProposal,
    FutureCapability,
    ViewDataset,
)
from entropia.infrastructure.postgres.models.create_package import (
    BaselineAsset,
    DependencyScan,
    PackageRequest,
    PackageValidationRun,
)
from entropia.infrastructure.postgres.models.deletion import Tombstone, TrashEntry
from entropia.infrastructure.postgres.models.esp import (
    EmbeddedResolverContract,
    EmbeddedResolverRegistry,
)
from entropia.infrastructure.postgres.models.export import ExportArtifact
from entropia.infrastructure.postgres.models.identity import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.models.instrument import (
    InstrumentAlias,
    InstrumentRegistry,
)
from entropia.infrastructure.postgres.models.jobs import IdempotencyKey, Job
from entropia.infrastructure.postgres.models.mainboard import (
    MainboardCompositionSnapshot,
    MainboardWorkingItem,
    MainboardWorkspace,
    WorkObjectRevision,
    WorkObjectRoot,
)
from entropia.infrastructure.postgres.models.manual import (
    ManualContentBlock,
    ManualDocument,
    ManualDocumentRevision,
    ManualPublicationEvent,
    ManualSearchChunk,
    ManualStreamEntry,
)
from entropia.infrastructure.postgres.models.market_data import (
    DatasetCoverageSlice,
    MarketDatasetRevision,
    MarketProcessedAsset,
    MarketRawAsset,
    MarketSchemaMapping,
    MarketValidationIssue,
    MarketValidationRun,
)
from entropia.infrastructure.postgres.models.metric_profile import (
    MetricDefinition,
    ResultViewMetricProfileRevision,
    ResultViewMetricProfileRoot,
)
from entropia.infrastructure.postgres.models.packages import PackageRevision, PackageRoot
from entropia.infrastructure.postgres.models.rationale import (
    PackageRationaleAssignment,
    RationaleFamilyRevision,
    RationaleFamilyRoot,
)
from entropia.infrastructure.postgres.models.readiness import (
    ReadinessIssueRow,
    ReadyCheckReport,
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
from entropia.infrastructure.postgres.models.strategy import (
    StrategyEditorDraft,
    StrategyRevision,
    StrategyRevisionReference,
    StrategyRoot,
)
from entropia.infrastructure.postgres.models.system import AppMetadata
from entropia.infrastructure.postgres.models.trade_log import CanonicalTradeRecordBatch
from entropia.infrastructure.postgres.models.trading_signal import (
    NormalizedSignalEventRevision,
    SourceAsset,
)

__all__ = [
    "Agent",
    "AgentCheckpoint",
    "AgentEvent",
    "AgentRuntime",
    "AgentTask",
    "AgentToolCall",
    "AnalysisArtifact",
    "AppMetadata",
    "ApprovalDecision",
    "ArtifactLink",
    "AuditEvent",
    "AuthSession",
    "BacktestResult",
    "BacktestRun",
    "BacktestRunManifest",
    "BaselineAsset",
    "CanonicalTradeRecordBatch",
    "CapabilityActivationEvent",
    "DatasetCoverageSlice",
    "DependencyScan",
    "DiagnosticArtifact",
    "EmbeddedResolverContract",
    "EmbeddedResolverRegistry",
    "EntityRegistry",
    "EntityRevision",
    "ExecutionPlan",
    "ExperimentProposal",
    "ExportArtifact",
    "FutureCapability",
    "HumanCredential",
    "HumanUser",
    "HypothesisArtifact",
    "IdempotencyKey",
    "InstrumentAlias",
    "InstrumentRegistry",
    "Job",
    "LabMessage",
    "MainboardCompositionSnapshot",
    "MainboardWorkingItem",
    "MainboardWorkspace",
    "ManualContentBlock",
    "ManualDocument",
    "ManualDocumentRevision",
    "ManualPublicationEvent",
    "ManualSearchChunk",
    "ManualStreamEntry",
    "MarketDatasetRevision",
    "MarketProcessedAsset",
    "MarketRawAsset",
    "MarketSchemaMapping",
    "MarketValidationIssue",
    "MarketValidationRun",
    "MetricDefinition",
    "MetricValueRow",
    "NormalizedSignalEventRevision",
    "OutboxEvent",
    "PackageRationaleAssignment",
    "PackageRequest",
    "PackageRevision",
    "PackageRoot",
    "PackageValidationRun",
    "PortfolioAllocationEntry",
    "PortfolioAllocationPlan",
    "PortfolioAllocationPlanRevision",
    "Principal",
    "RationaleFamilyRevision",
    "RationaleFamilyRoot",
    "ReadinessIssueRow",
    "ReadyCheckReport",
    "ResearchDatasetRevision",
    "ResearchFeatureDefinition",
    "ResearchFieldDefinition",
    "ResearchMarketLink",
    "ResearchNativeAsset",
    "ResearchRawAsset",
    "ResearchTimePolicy",
    "ResearchValidationIssue",
    "ResearchValidationRun",
    "ResultEquityPoint",
    "ResultManifestSnapshot",
    "ResultSummary",
    "ResultViewMetricProfileRevision",
    "ResultViewMetricProfileRoot",
    "SignalEventRow",
    "SourceAsset",
    "StrategyEditorDraft",
    "StrategyRevision",
    "StrategyRevisionReference",
    "StrategyRoot",
    "TaskDirective",
    "Tombstone",
    "TradeLedgerRow",
    "TrashEntry",
    "ViewDataset",
    "WorkObjectRevision",
    "WorkObjectRoot",
]
