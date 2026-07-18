"""
The watchdog. Runs on its own schedule and asks one question: "has crawling
actually been working?" If yes, stays silent. If no, sends one alert with a
plain-English explanation plus a ready-to-paste technical block.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select, desc

from app.database import celery_db_session
from app.models import CrawlRun, CrawlRunStatus, PortalSource
from app.services.diagnostics import diagnose_failure
from app.services.notifications import send_alert
from app.tasks.celery_app import celery_app

STALENESS_THRESHOLD_HOURS = 4
CONSECUTIVE_ZERO_RESULT_THRESHOLD = 5


@celery_app.task(name="app.tasks.watchdog_tasks.check_crawler_health")
def check_crawler_health():
    asyncio.run(_check_crawler_health_async())


async def _check_crawler_health_async():
    async with celery_db_session() as db:
        for portal in PortalSource:
            await _check_portal(db, portal.value)


async def _check_portal(db, portal: str):
    result = await db.execute(
        select(CrawlRun).where(CrawlRun.portal == portal).order_by(desc(CrawlRun.started_at)).limit(10)
    )
    recent_runs = result.scalars().all()

    if not recent_runs:
        return

    last_run = recent_runs[0]
    now = datetime.now(timezone.utc)
    staleness = now - last_run.started_at

    if staleness > timedelta(hours=STALENESS_THRESHOLD_HOURS):
        hours = staleness.total_seconds() / 3600
        await send_alert(
            subject=f"TenderPulse's {portal.upper()} checker has gone quiet",
            message=(
                f"WHAT'S WRONG: TenderPulse hasn't checked {portal.upper()} in {hours:.1f} hours.\n\n"
                f"LIKELY CAUSE: The background system that runs the checks may have stopped running, "
                f"possibly after a computer restart.\n\n"
                f"WHAT TO DO: Forward this whole email to your AI CTO (Claude) and ask it to help you "
                f"check if the system is still running (look for containers named 'worker' and 'beat' "
                f"in Docker Desktop -- if they're not there or show a red/stopped icon, that's the issue)."
            ),
        )
        logger.warning(f"[watchdog] {portal} stale: last run {staleness} ago")
        return

    if last_run.status == CrawlRunStatus.FAILED:
        recent_failures = sum(1 for r in recent_runs[:3] if r.status == CrawlRunStatus.FAILED)
        if recent_failures >= 3:
            diagnosis = diagnose_failure(portal, recent_runs)
            await send_alert(
                subject=f"TenderPulse's {portal.upper()} checker needs attention",
                message=(
                    f"WHAT'S WRONG: {diagnosis.plain_english_summary}\n\n"
                    f"LIKELY CAUSE: {diagnosis.likely_cause}\n\n"
                    f"WHAT TO DO: Copy this entire email and send it to your AI CTO (Claude).\n\n"
                    f"{diagnosis.technical_block}"
                ),
            )
            logger.warning(f"[watchdog] {portal} failing repeatedly: {last_run.error_message}")
        return

    recent_zero_results = sum(1 for r in recent_runs[:CONSECUTIVE_ZERO_RESULT_THRESHOLD] if r.listings_found == 0)
    if len(recent_runs) >= CONSECUTIVE_ZERO_RESULT_THRESHOLD and recent_zero_results == CONSECUTIVE_ZERO_RESULT_THRESHOLD:
        diagnosis = diagnose_failure(portal, recent_runs)
        await send_alert(
            subject=f"TenderPulse's {portal.upper()} checker may be broken (finding nothing)",
            message=(
                f"WHAT'S WRONG: {diagnosis.plain_english_summary}\n\n"
                f"LIKELY CAUSE: {diagnosis.likely_cause}\n\n"
                f"WHAT TO DO: Copy this entire email and send it to your AI CTO (Claude).\n\n"
                f"{diagnosis.technical_block}"
            ),
        )
        logger.warning(f"[watchdog] {portal} returning zero results for {CONSECUTIVE_ZERO_RESULT_THRESHOLD} runs")
