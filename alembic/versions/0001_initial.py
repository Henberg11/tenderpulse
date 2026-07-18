"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column("department", sa.String(500), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organisations_name", "organisations", ["name"])
    op.create_index("ix_organisations_normalized_name", "organisations", ["normalized_name"])

    op.create_table(
        "tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_number", sa.String(200), nullable=False),
        sa.Column("reference_number", sa.String(200), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "portal_source",
            sa.Enum("gem", "cppp", "state", "municipal", "psu", "railways", "other", name="portal_source"),
            nullable=False,
        ),
        sa.Column("portal_url", sa.Text(), nullable=True),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organisations.id"), nullable=True),
        sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("emd_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("tender_fee", sa.Numeric(18, 2), nullable=True),
        sa.Column("bid_submission_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bid_submission_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("technical_opening_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("financial_opening_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.String(200), nullable=True),
        sa.Column("matched_keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column(
            "status",
            sa.Enum("live", "closed", "cancelled", "awarded", "corrigendum_issued", name="tender_status"),
            nullable=False,
            server_default="live",
        ),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ai_executive_summary", sa.Text(), nullable=True),
        sa.Column("ai_eligibility_summary", sa.Text(), nullable=True),
        sa.Column("ai_risk_factors", sa.Text(), nullable=True),
        sa.Column("opportunity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("user_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenders_tender_number", "tenders", ["tender_number"])
    op.create_index("ix_tenders_portal_source", "tenders", ["portal_source"])
    op.create_index("ix_tenders_status", "tenders", ["status"])
    op.create_index("ix_tender_number_portal", "tenders", ["tender_number", "portal_source"], unique=True)

    op.create_table(
        "tender_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("ocr_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tender_documents_tender_id", "tender_documents", ["tender_id"])
    op.create_index("ix_tender_documents_content_hash", "tender_documents", ["content_hash"])

    op.create_table(
        "corrigenda",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("field_changed", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("importance", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("business_impact", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_documents.id"), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_corrigenda_tender_id", "corrigenda", ["tender_id"])

    op.create_table(
        "crawl_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portal", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "success", "failed", "partial", name="crawl_run_status"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("listings_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tenders_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("corrigenda_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("documents_downloaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_crawl_runs_portal", "crawl_runs", ["portal"])
    op.create_index("ix_crawl_runs_status", "crawl_runs", ["status"])


def downgrade() -> None:
    op.drop_table("crawl_runs")
    op.drop_table("corrigenda")
    op.drop_table("tender_documents")
    op.drop_table("tenders")
    op.drop_table("organisations")
    sa.Enum(name="crawl_run_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tender_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="portal_source").drop(op.get_bind(), checkfirst=True)
