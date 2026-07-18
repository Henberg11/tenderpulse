import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_number: str
    title: str
    portal_source: str
    estimated_value: float | None
    emd_amount: float | None
    bid_submission_end: datetime | None
    status: str
    matched_keywords: list[str] | None
    opportunity_score: float | None
    created_at: datetime


class CorrigendumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    field_changed: str
    old_value: str | None
    new_value: str | None
    importance: str
    detected_at: datetime
