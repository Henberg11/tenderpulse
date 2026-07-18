import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenderDocument(Base):
    """Every file attached to a tender: notice, BoQ, corrigendum PDF, etc.
    `content_hash` is how we detect 'this file already exists, skip it' and
    also how we detect 'this file replaced an older version'."""

    __tablename__ = "tender_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id"), index=True)
    tender: Mapped["Tender"] = relationship(back_populates="documents")

    file_name: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
