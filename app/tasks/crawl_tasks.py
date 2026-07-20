"""
Alpha Logic, corrected: the crawl itself now ONLY does Steps 1-4 -- find
Gujarat tenders, filter to genuinely relevant ones, save their basic
search-results-page info (title, department, dates, tender number). NO
document ever gets downloaded here, and NO AI ever gets called here.

This was a real mistake in the first Alpha Logic build -- it kept the old
automatic-download behavior inherited from before, directly contradicting
the actual spec: "getting the information about the tender... without
downloading the PDF" (Step 3), with download/analyze as dashboard OPTIONS
(Step 5), not automatic crawl behavior. Document downloading and AI
analysis now only happen on-demand, triggered from the dashboard (see
analyze_tasks.py) -- this crawl is purely discovery and cataloguing.

A pleasant side effect: this makes the crawl itself dramatically faster --
no document downloads, no Gemini pacing delays, just search-result pages.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select

from app.crawlers.base import browser_page
from app.crawlers.gem_crawler import GemCrawler
from app.database import celery_db_session
from app.models import PortalSource, CrawlRun, CrawlRunStatus
from app.services.ingestion import ingest_listing
from app.tasks.celery_app import celery_app
from app.tasks.digest_tasks import send_digest
from app.utils.keywords import SCHOOL_UNIFORM_KEYWORDS
from app.utils.redact import redact_secrets

OVERLAP_GUARD_MINUTES = 300


@celery_app.task(name="app.tasks.crawl_tasks.crawl_gem", bind=True, max_retries=3)
def crawl_gem(self):
    try:
        asyncio.run(_crawl_gem_async())
    except Exception as exc:
        logger.exception("[crawl_gem] task failed, will retry")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _crawl_gem_async():
    async with celery_db_session() as db:
        if await _already_running(db, PortalSource.GEM.value):
            logger.info("[crawl_gem] a crawl for GeM is already in progress, skipping this run")
            return

        run = CrawlRun(portal=PortalSource.GEM.value, status=CrawlRunStatus.RUNNING)
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            crawler = GemCrawler()

            async with browser_page() as page:
                # Step 1: every Gujarat tender, across every category, using
                # GeM's own Consignee State filter -- real ground truth, no
                # guessing. location="Gujarat" is set with full confidence
                # directly from this search, needing no document read.
                gujarat_listings = await crawler.search_by_consignee_state(page, "Gujarat")
                logger.info(f"[crawl_gem] {len(gujarat_listings)} total Gujarat tenders found (all categories)")

            run.listings_found = len(gujarat_listings)

            tenders_created = 0
            corrigenda_detected = 0

            for listing in gujarat_listings:
                # Steps 2+4: product-relevance and anomaly exclusion
                # (Panty/rack) happen inside ingest_listing() via
                # is_likely_relevant() -- pure text matching against the
                # title we already have from the search page, no document
                # needed. Saves ONLY search-results-page info: title,
                # department, dates, tender number.
                result = await ingest_listing(db, listing, PortalSource.GEM, SCHOOL_UNIFORM_KEYWORDS)
                await db.commit()
                if result is None:
                    continue
                tenders_created += 1
                corrigenda_detected += result.corrigenda_created

            run.tenders_created = tenders_created
            run.corrigenda_detected = corrigenda_detected
            run.documents_downloaded = 0  # never happens during crawl anymore, by design
            run.status = CrawlRunStatus.SUCCESS if gujarat_listings else CrawlRunStatus.PARTIAL
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            send_digest.delay()

        except Exception as e:
            run.status = CrawlRunStatus.FAILED
            run.error_message = redact_secrets(str(e))[:2000]
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            raise


async def _already_running(db, portal: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=OVERLAP_GUARD_MINUTES)
    result = await db.execute(
        select(CrawlRun).where(
            CrawlRun.portal == portal,
            CrawlRun.status == CrawlRunStatus.RUNNING,
            CrawlRun.started_at >= cutoff,
        )
    )
    return result.scalar_one_or_none() is not None
