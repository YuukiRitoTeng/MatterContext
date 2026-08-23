"""Persist safe structured-generation usage metadata.

Revision ID: 0004_structured_generation
Revises: 0003_document_ingestion
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_structured_generation"
down_revision = "0003_document_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("processing_runs") as batch:
        batch.add_column(sa.Column("usage_input_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("usage_output_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("usage_total_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("processing_runs") as batch:
        batch.drop_column("usage_total_tokens")
        batch.drop_column("usage_output_tokens")
        batch.drop_column("usage_input_tokens")
