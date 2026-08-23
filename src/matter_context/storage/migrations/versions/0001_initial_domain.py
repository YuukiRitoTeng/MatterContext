"""Initial matter, source, review, and Case Brief persistence.

Revision ID: 0001_initial_domain
Revises:
Create Date: 2026-08-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_domain"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("matters", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("title", sa.String(500), nullable=False), sa.Column("reference", sa.String(255)), sa.Column("description", sa.Text()), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("sources", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("matter_id", sa.String(36), sa.ForeignKey("matters.identifier"), nullable=False), sa.Column("kind", sa.String(32), nullable=False), sa.Column("provenance", sa.String(32), nullable=False), sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("text", sa.Text()), sa.Column("attachment_path", sa.String(1024)), sa.Column("original_filename", sa.String(1024)), sa.Column("media_type", sa.String(255)), sa.Column("correction_of_id", sa.String(36), sa.ForeignKey("sources.identifier")), sa.Column("ingestion_status", sa.String(32), nullable=False), sa.Column("extraction_status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sources_matter_id", "sources", ["matter_id"])
    op.create_table("content_blocks", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.identifier"), nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("locator", sa.String(1024)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("source_id", "ordinal", name="uq_content_block_source_ordinal"))
    op.create_index("ix_content_blocks_source_id", "content_blocks", ["source_id"])
    op.create_table("claims", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("matter_id", sa.String(36), sa.ForeignKey("matters.identifier"), nullable=False), sa.Column("statement", sa.Text(), nullable=False), sa.Column("category", sa.String(128), nullable=False), sa.Column("provenance", sa.String(32), nullable=False), sa.Column("revision_of_id", sa.String(36), sa.ForeignKey("claims.identifier"), unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_claims_matter_id", "claims", ["matter_id"])
    op.create_table("source_references", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.identifier"), nullable=False), sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.identifier")), sa.Column("content_block_id", sa.String(36), sa.ForeignKey("content_blocks.identifier")), sa.Column("page", sa.Integer()), sa.Column("paragraph", sa.Integer()), sa.Column("character_start", sa.Integer()), sa.Column("character_end", sa.Integer()), sa.Column("excerpt", sa.Text()))
    op.create_index("ix_source_references_claim_id", "source_references", ["claim_id"])
    op.create_table("review_decisions", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.identifier"), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("actor_kind", sa.String(32), nullable=False), sa.Column("actor_id", sa.String(255), nullable=False), sa.Column("note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_review_decisions_claim_id", "review_decisions", ["claim_id"])
    op.create_table("processing_runs", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("matter_id", sa.String(36), sa.ForeignKey("matters.identifier"), nullable=False), sa.Column("operation", sa.String(128), nullable=False), sa.Column("input_source_ids", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("provider", sa.String(255)), sa.Column("model", sa.String(255)), sa.Column("workflow_version", sa.String(255)), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("error_summary", sa.Text()))
    op.create_index("ix_processing_runs_matter_id", "processing_runs", ["matter_id"])
    op.create_table("case_brief_versions", sa.Column("identifier", sa.String(36), primary_key=True), sa.Column("matter_id", sa.String(36), sa.ForeignKey("matters.identifier"), nullable=False), sa.Column("source_ids", sa.Text(), nullable=False), sa.Column("claim_ids", sa.Text(), nullable=False), sa.Column("review_decision_ids", sa.Text(), nullable=False), sa.Column("workflow_version", sa.String(255), nullable=False), sa.Column("structured_payload", sa.Text(), nullable=False), sa.Column("rendered_text", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_case_brief_versions_matter_id", "case_brief_versions", ["matter_id"])


def downgrade() -> None:
    for table in ("case_brief_versions", "processing_runs", "review_decisions", "source_references", "claims", "content_blocks", "sources", "matters"):
        op.drop_table(table)
