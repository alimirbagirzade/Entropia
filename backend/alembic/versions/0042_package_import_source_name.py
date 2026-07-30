"""Pin the imported package's own name on the import job (F-07 §4.4)

The Library Import report identifies every job by a bare ``import_job_id`` — an
opaque id as the ONLY discriminator, which is exactly the F-07 defect ("no common
task requires recognizing an opaque identifier").

The honest label already exists in the evidence the job pins: an export manifest
carries ``name`` (``commands.package_lifecycle.export_package``). This adds a
nullable ``source_package_name`` column that ``submit_package_import`` fills from
the SUBMITTED manifest at submit time, alongside the ``manifest_hash`` it already
certifies. Capturing it at submit — rather than joining the resulting package root
later — keeps the label true for jobs that never produced a package (``blocked`` /
``failed``) and immune to a later rename of the imported copy.

Nullable on purpose and NOT backfilled: rows written before this migration never
observed a name, and inventing one for them would be a fabricated label. They read
back NULL and the UI falls back to the id.

Revision ID: 0042_package_import_source_name
Revises: 0041_filtered_event_artifact
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_package_import_source_name"
down_revision: str | None = "0041_filtered_event_artifact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "package_import_job"
_COLUMN = "source_package_name"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
