"""stage 7b — Future Dev (doc 22 §9, §9.1)

Six tables: future_capability (server-side Capability Registry with monotonic
per-row registry_version OCC token), capability_activation_event (immutable
append-only transition audit; UNIQUE (capability_id, resulting_registry_version)),
analysis_artifact + view_dataset (future output roots a Limited/Active
capability may create; deletion_state overlay for normal Trash rules),
experiment_proposal + execution_plan (future-only roots — the doc-22 contract
exists, no V1 command writes them, CR-09).

Seeds the seven fixed V18 capability slots as PLACEHOLDER registry rows with
deterministic ids (``fcap_<key>``) from the same ``BASELINE_CAPABILITIES``
content source tests use (doc 22 §4, §9).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.capability.baseline import BASELINE_CAPABILITIES, UI_SURFACE_VERSION_V18
from entropia.domain.capability.enums import CapabilityState
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0020_future_dev"
down_revision: str | None = "0019_user_manual"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_CAPABILITY_FK = "future_capability.capability_id"


def upgrade() -> None:
    # === future_capability (registry root; FK -> principals) ===
    op.create_table(
        "future_capability",
        sa.Column("capability_id", sa.String(40), primary_key=True),
        sa.Column("capability_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("menu_path", sa.String(160), nullable=False),
        sa.Column(
            "lifecycle_state",
            enum_column(CapabilityState, "capability_lifecycle_state"),
            nullable=False,
            server_default=CapabilityState.PLACEHOLDER.value,
        ),
        sa.Column("ui_surface_version", sa.String(32), nullable=False),
        sa.Column("domain_contract_version", sa.String(32), nullable=True),
        sa.Column("dependency_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("registry_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retirement_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changed_by_actor_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("change_reason", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("capability_key", name="uq_future_capability_key"),
    )
    op.create_index("ix_future_capability_state", "future_capability", ["lifecycle_state"])

    # === capability_activation_event (immutable audit; FK -> capability) ===
    op.create_table(
        "capability_activation_event",
        sa.Column("event_id", sa.String(40), primary_key=True),
        sa.Column("capability_id", sa.String(40), sa.ForeignKey(_CAPABILITY_FK), nullable=False),
        sa.Column("capability_key", sa.String(64), nullable=False),
        sa.Column(
            "from_state",
            enum_column(CapabilityState, "capability_event_from_state"),
            nullable=False,
        ),
        sa.Column(
            "to_state",
            enum_column(CapabilityState, "capability_event_to_state"),
            nullable=False,
        ),
        sa.Column("actor_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("dependency_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("snapshot_checksum", sa.String(64), nullable=False),
        sa.Column("prior_registry_version", sa.Integer(), nullable=False),
        sa.Column("resulting_registry_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "capability_id",
            "resulting_registry_version",
            name="uq_capability_event_registry_version",
        ),
    )
    op.create_index("ix_capability_events_key", "capability_activation_event", ["capability_key"])

    # === analysis_artifact (future output root; FK -> principals) ===
    op.create_table(
        "analysis_artifact",
        sa.Column("artifact_id", sa.String(40), primary_key=True),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("capability_key", sa.String(64), nullable=False),
        sa.Column("input_manifest_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("method_version", sa.String(64), nullable=False),
        sa.Column("output_ref", sa.String(255), nullable=True),
        sa.Column(
            "deletion_state",
            enum_column(DeletionState, "analysis_artifact_deletion_state"),
            nullable=False,
            server_default=DeletionState.ACTIVE.value,
        ),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_analysis_artifact_type", "analysis_artifact", ["artifact_type"])
    op.create_index("ix_analysis_artifact_capability", "analysis_artifact", ["capability_key"])

    # === view_dataset (future output root; FK -> principals) ===
    op.create_table(
        "view_dataset",
        sa.Column("view_dataset_id", sa.String(40), primary_key=True),
        sa.Column("capability_key", sa.String(64), nullable=False),
        sa.Column("source_manifest_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("series_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("marker_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("range_spec", postgresql.JSONB(), nullable=True),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column(
            "deletion_state",
            enum_column(DeletionState, "view_dataset_deletion_state"),
            nullable=False,
            server_default=DeletionState.ACTIVE.value,
        ),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_view_dataset_capability", "view_dataset", ["capability_key"])

    # === experiment_proposal (future-only root; FK -> principals) ===
    op.create_table(
        "experiment_proposal",
        sa.Column("proposal_id", sa.String(40), primary_key=True),
        sa.Column("hypothesis_ref", sa.String(64), nullable=True),
        sa.Column("input_bundle_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("parameter_plan_ref", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("acceptance_criteria", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # === execution_plan (future-only Live Trade root; FK -> principals) ===
    op.create_table(
        "execution_plan",
        sa.Column("plan_id", sa.String(40), primary_key=True),
        sa.Column("strategy_revision_ref", sa.String(64), nullable=True),
        sa.Column("package_revision_ref", sa.String(64), nullable=True),
        sa.Column("market_data_policy_ref", sa.String(64), nullable=True),
        sa.Column("portfolio_ref", sa.String(64), nullable=True),
        sa.Column("execution_policy_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("lifecycle_state", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # === baseline registry seed (doc 22 §4, §9 — seven PLACEHOLDER slots) ===
    registry_stub = sa.table(
        "future_capability",
        sa.column("capability_id", sa.String(40)),
        sa.column("capability_key", sa.String(64)),
        sa.column("title", sa.String(120)),
        sa.column("menu_path", sa.String(160)),
        sa.column("lifecycle_state", sa.String(32)),
        sa.column("ui_surface_version", sa.String(32)),
        sa.column("dependency_snapshot", postgresql.JSONB()),
        sa.column("registry_version", sa.Integer()),
    )
    op.bulk_insert(
        registry_stub,
        [
            {
                "capability_id": seed.capability_id,
                "capability_key": seed.capability_key,
                "title": seed.title,
                "menu_path": seed.menu_path,
                "lifecycle_state": CapabilityState.PLACEHOLDER.value,
                "ui_surface_version": UI_SURFACE_VERSION_V18,
                "dependency_snapshot": seed.dependency_snapshot,
                "registry_version": 1,
            }
            for seed in BASELINE_CAPABILITIES
        ],
    )


def downgrade() -> None:
    op.drop_table("capability_activation_event")
    op.drop_table("analysis_artifact")
    op.drop_table("view_dataset")
    op.drop_table("experiment_proposal")
    op.drop_table("execution_plan")
    op.drop_table("future_capability")
