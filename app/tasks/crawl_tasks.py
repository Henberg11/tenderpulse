"""
Alpha Logic: narrowed to Gujarat only, per explicit decision. Real
simplification, not just a scope cut -- since Gujarat-relevance now comes
directly from GeM's own Consignee State filter (ground truth) rather than
from downloading and reading a PDF to find out, or from hoping a tender
survived nationwide keyword-search pagination, the whole separate
nationwide multi-keyword search phase is no longer needed at all. One
search establishes Gujarat-relevance; our own local text matching
establishes product-relevance; only tenders that pass BOTH ever get a
document downloaded.

This should cut crawl time dramatically versus the old approach (12
nationwide searches, each up to 12 pages, downloading documents for
potentially hundreds of eventually-irrelevant tenders just to find out
their state) -- one Gujarat search, document downloads only for the
smaller subset that's already confirmed relevant on both fronts.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select

from app.config import settings
from app.crawlers.base import browser_page
from app.crawlers.gem_crawler import GemCrawler
from app.database import celery_db_session
from app.models import PortalSource, CrawlRun, CrawlRunStatus
from app.services.document_intelligence import process_downloaded_document
from app.services.ingestion import ingest_listing
from app.tasks.celery_app import celery_app
from app.tasks.digest_tasks import send_digest
from app.utils.keywords import SCHOOL_UNIFORM_KEYWORDS, matches_any_keyword
from app.utils.redact import redact_secrets

# If a crawl for this portal is still marked RUNNING and started more
# recently than this, assume it's genuinely in progress and skip. A RUNNING
# row older than this is assumed to be an orphan from a crashed worker.
# Also auto-recovered by the watchdog (see watchdog_tasks.py) well before
# this guard would ever matter in practice -- this is a secondary safety
# net, not the primary recovery mechanism anymore.
OVERLAP_GUARD_MINUTES = 300

# Pause after any document that triggered a Gemini call. Gemini's free tier
# allows roughly 10-15 requests per minute -- processing documents
# back-to-back with no gap reliably hit that limit during real testing.
GEMINI_PACING_SECONDS = 8

# Pause after every document download, even ones that don't call Gemini --
# stays a polite, rate-limited visitor to GeM per our own compliance
# principles (ROADMAP.md).
DOWNLOAD_PACING_SECONDS = 2


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
                # GeM's own Consignee State filter -- real ground truth, not
                # a guess. Each listing already has location="Gujarat" set
                # with full confidence, no PDF needed to know that.
                gujarat_listings = await crawler.search_by_consignee_state(page, "Gujarat")
                logger.info(f"[crawl_gem] {len(gujarat_listings)} total Gujarat tenders found (all categories)")

                # Step 2 + 4: product-relevance and anomaly exclusion
                # (Panty/rack) happen inside ingest_listing() below via
                # is_likely_relevant() -- not duplicated here, so that
                # check stays defined in exactly one place (keywords.py).
                run.listings_found = len(gujarat_listings)

                tenders_created = 0
                corrigenda_detected = 0
                documents_downloaded = 0

                for listing in gujarat_listings:
                    result = await ingest_listing(db, listing, PortalSource.GEM, SCHOOL_UNIFORM_KEYWORDS)
                    await db.commit()
                    if result is None:
                        # Failed the relevance check (see is_likely_relevant
                        # in keywords.py, includes the Panty/rack anomaly
                        # exclusions) -- not a genuine uniform tender, skip
                        # entirely.
                        continue
                    tenders_created += 1
                    corrigenda_detected += result.corrigenda_created

                    is_precise_match = bool(matches_any_keyword(listing.title, SCHOOL_UNIFORM_KEYWORDS))

                    # Step 3/5: only NOW, for a tender already confirmed both
                    # Gujarat-relevant AND product-relevant, do we download
                    # and read its document -- exactly the "common ones
                    # only" principle. AI summarization still only runs for
                    # Core Matches (run_ai_summary), same as before.
                    dest_dir = f"{settings.storage_dir}/{result.tender.tender_number}"
                    try:
                        paths = await crawler.download_documents(page, listing, dest_dir)
                        documents_downloaded += len(paths)
                        logger.info(f"[crawl_gem] downloaded {len(paths)} docs for {result.tender.tender_number}")

                        for path in paths:
                            try:
                                await process_downloaded_document(
                                    db, result.tender, path, listing.portal_url, run_ai_summary=is_precise_match
                                )
                                await db.commit()
                                await asyncio.sleep(GEMINI_PACING_SECONDS if is_precise_match else DOWNLOAD_PACING_SECONDS)
                            except Exception:
                                logger.exception(f"[crawl_gem] document intelligence failed for {path}")
                    except Exception:
                        logger.exception(f"[crawl_gem] document download failed for {result.tender.tender_number}")

            run.tenders_created = tenders_created
            run.corrigenda_detected = corrigenda_detected
            run.documents_downloaded = documents_downloaded
            run.status = CrawlRunStatus.SUCCESS if gujarat_listings else CrawlRunStatus.PARTIAL
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            # Chained here, not scheduled independently -- this guarantees
            # the digest never fires before this crawl's real data is
            # ready. Its own "skip if nothing new" logic (digest_tasks.py)
            # decides whether an email actually gets sent.
            send_digest.delay()

        except Exception as e:
            run.status = CrawlRunStatus.FAILED
            # redact_secrets: some database drivers echo the full connection
            # string (password included) back inside their own exception
            # messages -- without this, a connection failure could leak the
            # Supabase password into this row, and from there into a
            # watchdog alert email.
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
