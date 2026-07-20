"""
Handles "Analyze this tender" requests from the dashboard, without the
dashboard ever touching the Gemini key directly. Tapping the button just
sets a flag (analyze_requested = true) via the same narrow, column-scoped
write permission already used for Track/Applied -- this task checks for
that flag every few minutes and does the actual work here, where the key
has always safely lived.

Rebuilt: the crawl itself no longer downloads any documents at all (see
crawl_tasks.py) -- discovery and document-reading are now fully separate,
matching the actual intended design ("options like download document and
analyze document" as dashboard actions, not automatic crawl behavior).
This means analysis now genuinely does the whole job on demand: download
the document fresh from GeM, extract its text, pull out free structured
fields, and call Gemini -- reusing the exact same, already-proven pipeline
(process_downloaded_document) the old automatic-download crawl used, just
triggered by a dashboard click instead of happening automatically.
"""
import asyncio

from loguru import logger
from sqlalchemy import select

from app.config import settings
from app.crawlers.base import browser_page, RawTenderListing
from app.crawlers.gem_crawler import GemCrawler
from app.database import celery_db_session
from app.models import Tender
from app.services.document_intelligence import process_downloaded_document
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.analyze_tasks.process_analysis_requests")
def process_analysis_requests():
    asyncio.run(_process_analysis_requests_async())


async def _process_analysis_requests_async():
    async with celery_db_session() as db:
        result = await db.execute(select(Tender).where(Tender.analyze_requested == True))  # noqa: E712
        requested = result.scalars().all()

        if not requested:
            return

        logger.info(f"[analyze] {len(requested)} tender(s) requested for on-demand analysis")

        crawler = GemCrawler()
        async with browser_page() as page:
            for tender in requested:
                try:
                    await _analyze_one(db, page, crawler, tender)
                except Exception:
                    logger.exception(f"[analyze] failed to analyze {tender.tender_number}")
                finally:
                    # Always clear the flag, even on failure -- otherwise a
                    # tender that genuinely fails (bad download, Gemini
                    # error) would get retried every few minutes forever.
                    # The person can just tap "Analyze" again later.
                    tender.analyze_requested = False
                    await db.commit()


async def _analyze_one(db, page, crawler: GemCrawler, tender: Tender) -> None:
    if not tender.portal_url:
        logger.info(f"[analyze] {tender.tender_number} has no portal_url stored, can't download its document")
        return

    # Reconstruct just enough of a listing to reuse the existing, already-
    # proven download function -- it only ever needed portal_url and
    # tender_number, both of which are already stored on every Tender row.
    listing = RawTenderListing(
        tender_number=tender.tender_number,
        title=tender.title,
        portal_url=tender.portal_url,
    )

    dest_dir = f"{settings.storage_dir}/{tender.tender_number}"
    paths = await crawler.download_documents(page, listing, dest_dir)
    if not paths:
        logger.info(f"[analyze] no document downloaded for {tender.tender_number}")
        return

    for path in paths:
        # run_ai_summary=True always here -- unlike the automatic crawl
        # (which only AI-summarizes Core Matches to conserve quota), an
        # explicit "Analyze this tender" click is by definition a request
        # for the AI summary specifically, regardless of Core Match status.
        await process_downloaded_document(db, tender, path, tender.portal_url, run_ai_summary=True)
        await db.commit()

    logger.info(f"[analyze] on-demand analysis complete for {tender.tender_number}")
