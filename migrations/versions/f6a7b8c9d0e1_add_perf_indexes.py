"""add_perf_indexes

Add indexes on frequently queried FK columns and filter columns
for snapshot.run_id, snapshot.report_id, and alert.severity.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-22 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_snapshots_run_id", "snapshots", ["run_id"], if_not_exists=True)
    op.create_index("ix_snapshots_report_id", "snapshots", ["report_id"], if_not_exists=True)
    op.create_index("ix_alerts_severity", "alerts", ["severity"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_alerts_severity", table_name="alerts", if_exists=True)
    op.drop_index("ix_snapshots_report_id", table_name="snapshots", if_exists=True)
    op.drop_index("ix_snapshots_run_id", table_name="snapshots", if_exists=True)
