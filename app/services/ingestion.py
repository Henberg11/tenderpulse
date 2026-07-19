"""
Turns raw crawler output into DB rows, and detects corrigenda by diffing
incoming data against what's already stored.
"""
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawlers.base import RawTenderListing
from app.models import Tender, TenderStatus, PortalSource, Corrigendum, Organisation
from app.utils.indian_states import extract_state
from app.utils.keywords import matches_any_keyword

TRACKED_FIELDS = ["title", "estimated_value", "emd_amount", "bid_submission_end"]


@dataclass
class IngestResult:
    tender: Tender
    corrigenda_created: int


async def get_or_create_organisation(db: AsyncSession, name: str | None) -> Organisation | None:
    if not name:
        return None
    normalized = name.strip().lower()
    result = await db.execute(select(Organisation).where(Organisation.normalized_name == normalized))
    org = result.scalar_one_or_none()
    if org:
        return org

    org = Organisation(name=name.strip(), normalized_name=normalized)
    db.add(org)
    await db.flush()
    return org


async def ingest_listing(
    db: AsyncSession,
    listing: RawTenderListing,
    portal: PortalSource,
    keywords: list[str],
) -> IngestResult:
    """Insert a new tender, or update an existing one and record any
    corrigenda for fields that changed. Returns both the Tender row and how
    many corrigenda were created -- the caller (crawl_tasks.py) uses that
    count for the CrawlRun audit log, which previously always showed 0 here
    because this function only ever returned the Tender, silently dropping
    the corrigendum count."""

    result = await db.execute(
        select(Tender).where(
            Tender.tender_number == listing.tender_number,
            Tender.portal_source == portal,
        )
    )
    existing = result.scalar_one_or_none()

    org = await get_or_create_organisation(db, listing.organisation_name)
    matched = matches_any_keyword(listing.title, keywords)
    # GeM doesn't give state as its own field on the search results page, but
    # it's usually embedded in the department/address text (e.g. "...
    # Department Madhya Pradesh") -- extract it so tenders can be filtered
    # by state on the dashboard. Central bodies (Ministry of Defence,
    # Railways, etc.) correctly return None here -- they're national, not
    # state-specific, not a missing-data bug.
    state = listing.location or extract_state(listing.organisation_name)

    if existing is None:
        tender = Tender(
            tender_number=listing.tender_number,
            reference_number=listing.reference_number,
            title=listing.title,
            portal_source=portal,
            portal_url=listing.portal_url,
            organisation_id=org.id if org else None,
            estimated_value=listing.estimated_value,
            emd_amount=listing.emd_amount,
            bid_submission_end=listing.bid_submission_end,
            location=state,
            matched_keywords=matched,
            status=TenderStatus.LIVE,
        )
        db.add(tender)
        await db.flush()
        logger.info(f"[ingest] new tender {tender.tender_number} ({portal.value})")
        return IngestResult(tender=tender, corrigenda_created=0)

    new_values = {
        "title": listing.title,
        "estimated_value": listing.estimated_value,
        "emd_amount": listing.emd_amount,
        "bid_submission_end": listing.bid_submission_end,
    }
    corrigenda_created = 0
    for field in TRACKED_FIELDS:
        old_val = getattr(existing, field)
        new_val = new_values.get(field)
        if new_val is not None and str(old_val) != str(new_val):
            db.add(
                Corrigendum(
                    tender_id=existing.id,
                    field_changed=field,
                    old_value=str(old_val),
                    new_value=str(new_val),
                    importance="high" if field == "bid_submission_end" else "medium",
                )
            )
            setattr(existing, field, new_val)
            corrigenda_created += 1
            logger.info(f"[ingest] corrigendum detected on {existing.tender_number}: {field} changed")

    if corrigenda_created:
        existing.version_number += 1
        existing.status = TenderStatus.CORRIGENDUM_ISSUED

    # Backfill for tenders saved before state extraction existed -- without
    # this, every tender already in the database would stay blank forever,
    # since only *new* tenders would get this field populated.
    if not existing.location and state:
        existing.location = state

    await db.flush()
    return IngestResult(tender=existing, corrigenda_created=corrigenda_created)
