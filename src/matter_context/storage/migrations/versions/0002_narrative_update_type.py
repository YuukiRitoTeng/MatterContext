"""Store the selected category for immutable narrative updates.

Revision ID: 0002_narrative_update_type
Revises: 0001_initial_domain
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_narrative_update_type"
down_revision = "0001_initial_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("update_type", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "update_type")
