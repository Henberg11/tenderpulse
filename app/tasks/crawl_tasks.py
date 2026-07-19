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
from app.utils.keywords import GEM_SEARCH_TERMS, SCHOOL_UNIFORM_KEYWORDS, matches_any_keyword
from app.utils.redact import redact_secrets

# If a crawl for this portal is still marked RUNNING and started more
# recently than this, assume it's genuinely in progress and skip -- two
# overlapping crawls would double the request rate against GeM (violates our
# own rate-limiting principle, see ROADMAP.md) and could interleave writes in
# confusing ways. A RUNNING row older than this is assumed to be an orphan
# from a crashed worker, not a real overlap, so we proceed anyway rather than
# blocking forever.
#
# Raised from 30 to 90 to 300: crawls now paginate fully (see
# MAX_PAGES_PER_KEYWORD / MAX_CONSIGNEE_SEARCH_PAGES in gem_crawler.py)
# rather than stopping at a small page cap, and could legitimately take
# several hours. 300 minutes (5 hours) stays comfortably shorter than the
# 7.5-hour gap between the two scheduled daily runs (9 AM / 4:30 PM) --
# a genuinely stuck row from a crashed worker still self-heals well before
# the next automatic attempt, without needing manual intervention.
OVERLAP_GUARD_MINUTES = 300

# Pause after any document that triggered a Gemini call. Gemini's free tier
# allows roughly 10-15 requests per minute -- processing documents
# back-to-back with no gap reliably hit that limit during real testing.
GEMINI_PACING_SECONDS = 8

# Pause after EVERY document download, even ones that don't call Gemini.
# Downloads now happen for every genuine uniform tender, not just Core
# Matches (a real volume increase, ~10 to potentially 80-90 per crawl) --
# this keeps us being a polite, rate-limited visitor to GeM per our own
# compliance principles (ROADMAP.md), not just avoiding Gemini's limit.
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
                # One browser, one page, reused for the entire run -- both
                # the search phase and every document download after it.
                all_listings = await crawler.search(page, GEM_SEARCH_TERMS)
                logger.info(f"[crawl_gem] {len(all_listings)} raw listings found via keyword search")

                # Independent safety net: uses GeM's own structured
                # Consignee State filter (real data, not a text guess),
                # completely immune to the "what if it's on page 6"
                # nationwide-pagination problem the keyword search still
                # has. Confirmed necessary via a real, direct comparison
                # against a competitor's results this session -- keyword
                # search alone missed genuine Gujarat tenders, including
                # one with the word "Uniform" right in its title, because
                # nationwide sorting pushed it past page 1.
                try:
                    consignee_listings = await crawler.search_by_consignee_state(page, "Gujarat")
                    existing_numbers = {l.tender_number for l in all_listings}
                    caught_by_safety_net = 0
                    for listing in consignee_listings:
                        if listing.tender_number in existing_numbers:
                            continue
                        if matches_any_keyword(listing.title, SCHOOL_UNIFORM_KEYWORDS):
                            all_listings.append(listing)
                            existing_numbers.add(listing.tender_number)
                            caught_by_safety_net += 1
                    logger.info(
                        f"[crawl_gem] consignee-state safety net: {len(consignee_listings)} Gujarat tenders "
                        f"checked, {caught_by_safety_net} genuinely new ones caught that keyword search missed"
                    )
                except Exception:
                    # This is a safety net, not the primary path -- if it
                    # fails (e.g. GeM's page structure doesn't match our
                    # best-guess selectors yet), the regular keyword search
                    # results above are completely unaffected.
                    logger.exception("[crawl_gem] consignee-state safety net failed, continuing with keyword results only")

                # We DON'T discard anything here. Every genuine uniform-related
                # tender gets saved -- title, department, dates -- so nothing
                # is ever silently hidden.
                run.listings_found = len(all_listings)

                tenders_created = 0
                corrigenda_detected = 0
                documents_downloaded = 0

                for listing in all_listings:
                    result = await ingest_listing(db, listing, PortalSource.GEM, SCHOOL_UNIFORM_KEYWORDS)
                    await db.commit()
                    if result is None:
                        # Failed the relevance check (see is_likely_relevant
                        # in keywords.py) -- not a genuine uniform tender,
                        # skip it entirely rather than downloading its
                        # document or counting it.
                        continue
                    tenders_created += 1
                    corrigenda_detected += result.corrigenda_created

                    is_precise_match = bool(matches_any_keyword(listing.title, SCHOOL_UNIFORM_KEYWORDS))

                    # Every genuine tender's document now gets downloaded and
                    # freely read (location, EMD, category -- no AI cost) --
                    # not just Core Matches. This is what actually fills in
                    # location for the majority of tenders, which previously
                    # stayed blank forever unless they happened to precisely
                    # match your core product keywords. AI summarization
                    # (Gemini) still only runs for Core Matches, controlled
                    # by run_ai_summary below -- this doesn't touch your AI
                    # quota any more than before.
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
            run.status = CrawlRunStatus.SUCCESS if all_listings else CrawlRunStatus.PARTIAL
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
