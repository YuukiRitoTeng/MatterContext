"""Persist document ingestion state and block references.

Revision ID: 0003_document_ingestion
Revises: 0002_narrative_update_type
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_document_ingestion"
down_revision = "0002_narrative_update_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("duplicate_of_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_sources_duplicate_of", "sources", ["duplicate_of_id"], ["identifier"])
    with op.batch_alter_table("content_blocks") as batch:
        batch.add_column(sa.Column("page", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("paragraph", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("character_start", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("character_end", sa.Integer(), nullable=True))
    with op.batch_alter_table("processing_runs") as batch:
        batch.add_column(sa.Column("parser_name", sa.String(128), nullable=True))
        batch.add_column(sa.Column("parser_version", sa.String(128), nullable=True))
        batch.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("processing_runs") as batch:
        batch.drop_column("duration_ms")
        batch.drop_column("parser_version")
        batch.drop_column("parser_name")
    with op.batch_alter_table("content_blocks") as batch:
        batch.drop_column("character_end")
        batch.drop_column("character_start")
        batch.drop_column("paragraph")
        batch.drop_column("page")
    with op.batch_alter_table("sources") as batch:
        batch.drop_constraint("fk_sources_duplicate_of", type_="foreignkey")
        batch.drop_column("duplicate_of_id")
