"""add_site_type_to_calibration_samples

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-02-08 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add site_type column to calibration_samples
    op.execute(
        """
        ALTER TABLE calibration_samples
        ADD COLUMN IF NOT EXISTS site_type VARCHAR(50)
        """
    )

    # Create index for site_type queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_site_type "
        "ON calibration_samples(site_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_calibration_samples_site_type")
    op.execute("ALTER TABLE calibration_samples DROP COLUMN IF EXISTS site_type")
