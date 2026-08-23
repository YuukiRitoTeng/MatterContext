"""SQLAlchemy persistence records. Domain objects remain SQLAlchemy-free."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MatterRow(Base):
    __tablename__ = "matters"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SourceRow(Base):
    __tablename__ = "sources"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.identifier"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(String(1024))
    original_filename: Mapped[str | None] = mapped_column(String(1024))
    media_type: Mapped[str | None] = mapped_column(String(255))
    correction_of_id: Mapped[str | None] = mapped_column(ForeignKey("sources.identifier"))
    duplicate_of_id: Mapped[str | None] = mapped_column(ForeignKey("sources.identifier"))
    ingestion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    update_type: Mapped[str | None] = mapped_column(String(32))


class ContentBlockRow(Base):
    __tablename__ = "content_blocks"
    __table_args__ = (UniqueConstraint("source_id", "ordinal", name="uq_content_block_source_ordinal"),)
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.identifier"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(1024))
    page: Mapped[int | None] = mapped_column(Integer)
    paragraph: Mapped[int | None] = mapped_column(Integer)
    character_start: Mapped[int | None] = mapped_column(Integer)
    character_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimRow(Base):
    __tablename__ = "claims"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.identifier"), nullable=False, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_of_id: Mapped[str | None] = mapped_column(ForeignKey("claims.identifier"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SourceReferenceRow(Base):
    __tablename__ = "source_references"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.identifier"), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.identifier"))
    content_block_id: Mapped[str | None] = mapped_column(ForeignKey("content_blocks.identifier"))
    page: Mapped[int | None] = mapped_column(Integer)
    paragraph: Mapped[int | None] = mapped_column(Integer)
    character_start: Mapped[int | None] = mapped_column(Integer)
    character_end: Mapped[int | None] = mapped_column(Integer)
    excerpt: Mapped[str | None] = mapped_column(Text)


class ReviewDecisionRow(Base):
    __tablename__ = "review_decisions"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.identifier"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProcessingRunRow(Base):
    __tablename__ = "processing_runs"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.identifier"), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    input_source_ids: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    workflow_version: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(Text)
    parser_name: Mapped[str | None] = mapped_column(String(128))
    parser_version: Mapped[str | None] = mapped_column(String(128))
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class CaseBriefVersionRow(Base):
    __tablename__ = "case_brief_versions"
    identifier: Mapped[str] = mapped_column(String(36), primary_key=True)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.identifier"), nullable=False, index=True)
    source_ids: Mapped[str] = mapped_column(Text, nullable=False)
    claim_ids: Mapped[str] = mapped_column(Text, nullable=False)
    review_decision_ids: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(255), nullable=False)
    structured_payload: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
