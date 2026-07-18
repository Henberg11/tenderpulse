import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Numeric, ForeignKey, Enum, Index, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenderStatus(str, enum.Enum):
    LIVE = "live"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    AWARDED = "awarded"
    CORRIGENDUM_ISSUED = "corrigendum_issued"


class PortalSource(str, enum.Enum):
    GEM = "gem"
    CPPP = "cppp"
    STATE = "state"
    MUNICIPAL = "municipal"
    PSU = "psu"
    RAILWAYS = "railways"
    OTHER = "other"


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        Index("ix_tender_number_portal", "tender_number", "portal_source", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tender_number: Mapped[str] = mapped_column(String(200), index=True)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    portal_source: Mapped[PortalSource] = mapped_column(
        Enum(PortalSource, name="portal_source", values_callable=lambda obj: [e.value for e in obj]), index=True
    )
    portal_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    organisation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organisations.id"), nullable=True)
    organisation: Mapped["Organisation"] = relationship(back_populates="tenders")

    estimated_value: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    emd_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    tender_fee: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    bid_submission_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bid_submission_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    technical_opening_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    financial_opening_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    matched_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, name="tender_status", values_callable=lambda obj: [e.value for e in obj]),
        default=TenderStatus.LIVE,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(default=1)

    ai_executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_eligibility_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_risk_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    user_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["TenderDocument"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    corrigenda: Mapped[list["Corrigendum"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
