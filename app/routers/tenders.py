import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Tender, Corrigendum
from app.schemas.tender import TenderOut, CorrigendumOut

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("", response_model=list[TenderOut])
async def list_tenders(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    stmt = select(Tender).order_by(Tender.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Tender.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{tender_id}", response_model=TenderOut)
async def get_tender(tender_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        # A previous version returned {"error": "not found"} with a 200
        # status here -- wrong on two counts: wrong HTTP status for a
        # missing resource, AND it didn't match the declared TenderOut
        # response_model at all, which would fail FastAPI's own response
        # validation. A proper 404 is both more correct and more honest.
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    return tender


@router.get("/{tender_id}/corrigenda", response_model=list[CorrigendumOut])
async def get_tender_corrigenda(tender_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Corrigendum).where(Corrigendum.tender_id == tender_id).order_by(Corrigendum.detected_at.desc())
    )
    return result.scalars().all()
