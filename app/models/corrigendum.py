import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Corrigendum(Base):
    """One detected change to a tender. A single corrigendum document can
    produce multiple Corrigendum rows if it changes multiple fields
    (e.g. deadline AND EMD in the same amendment)."""

    __tablename__ = "corrigenda"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id"), index=True)
    tender: Mapped["Tender"] = relationship(back_populates="corrigenda")

    field_changed: Mapped[str] = mapped_column(String(100))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    importance: Mapped[str] = mapped_column(String(20), default="medium")
    business_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tender_documents.id"), nullable=True)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
