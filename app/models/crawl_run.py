import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrawlRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class CrawlRun(Base):
    """One row per crawl attempt. This is what lets the system know its own
    health without a human checking logs -- the watchdog task queries this
    table to decide whether to send an alert."""

    __tablename__ = "crawl_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portal: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[CrawlRunStatus] = mapped_column(
        Enum(CrawlRunStatus, name="crawl_run_status", values_callable=lambda obj: [e.value for e in obj]),
        default=CrawlRunStatus.RUNNING,
        index=True,
    )

    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    tenders_created: Mapped[int] = mapped_column(Integer, default=0)
    corrigenda_detected: Mapped[int] = mapped_column(Integer, default=0)
    documents_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
