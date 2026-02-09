"""add_entity_recognition_weight

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-02-02 14:00:00.000000

Adds weight_entity_recognition column to calibration_configs table.
This addresses the 23% pessimism bias by capturing external brand/entity
awareness signals (Wikipedia, Wikidata, domain age, web presence).

Weight redistribution (7 pillars, sum=100):
- technical: 15 -> 12
- structure: 20 -> 18
- schema: 15 -> 13
- authority: 15 -> 12
- entity_recognition: 13 (NEW)
- retrieval: 25 -> 22
- coverage: 10 -> 10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add weight_entity_recognition column with default value (idempotent)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'calibration_configs' "
            "AND column_name = 'weight_entity_recognition'"
        )
    )
    if not result.fetchone():
        op.add_column(
            "calibration_configs",
            sa.Column(
                "weight_entity_recognition",
                sa.Float(),
                nullable=False,
                server_default="13.0",
            ),
        )

    # Update default values for existing weights in new configs
    # Note: Existing configs retain their values, only new defaults change
    # This is handled by the model defaults, but we document the intent here
    #
    # For existing configs that use old defaults, we need to redistribute:
    # If they haven't been customized, the sum will be 100 (old defaults)
    # After adding entity_recognition=13, sum becomes 113, which is invalid
    #
    # We'll leave existing configs as-is (they still work with 6 pillars)
    # New configs will get the new 7-pillar defaults

    # Optionally: Update existing active configs to include entity_recognition
    # by proportionally reducing other weights. This is a policy decision.
    # For now, we just add the column and let manual recalibration handle it.


def downgrade() -> None:
    # Remove the entity_recognition weight column
    op.drop_column("calibration_configs", "weight_entity_recognition")
