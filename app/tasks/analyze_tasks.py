"""
Handles "Analyze this tender" requests from the dashboard, without the
dashboard ever touching the Gemini key directly. Tapping the button just
sets a flag (analyze_requested = true) via the same narrow, column-scoped
write permission already used for Track/Applied -- this task checks for
that flag every few minutes and does the actual Gemini call here, where the
key has always safely lived.

This exists specifically because the original design (calling Gemini
directly from the browser) required exposing the API key in public code,
which GitHub's own secret scanner correctly blocked. Same end result for
the person using the dashboard -- tap a button, get an analysis within a
few minutes -- with the key never leaving the server.
"""
import asyncio

from loguru import logger
from sqlalchemy import select

from app.database import celery_db_session
from app.models import Tender, TenderDocument
from app.services.document_intelligence import summarize_with_gemini
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

        for tender in requested:
            try:
                await _analyze_one(db, tender)
            except Exception:
                logger.exception(f"[analyze] failed to analyze {tender.tender_number}")
            finally:
                # Always clear the flag, even on failure -- otherwise a
                # tender with no document yet (or a genuine Gemini error)
                # would get retried every few minutes forever. The person
                # can just tap "Analyze" again later if it didn't work.
                tender.analyze_requested = False
                await db.commit()


async def _analyze_one(db, tender: Tender) -> None:
    doc_result = await db.execute(
        select(TenderDocument).where(TenderDocument.tender_id == tender.id).order_by(TenderDocument.id.desc()).limit(1)
    )
    doc = doc_result.scalar_one_or_none()

    if not doc or not doc.extracted_text:
        logger.info(f"[analyze] no document text available yet for {tender.tender_number}, skipping")
        return

    ai_result = await summarize_with_gemini(doc.extracted_text)
    if not ai_result:
        logger.info(f"[analyze] Gemini summarization failed for {tender.tender_number} (see error above, if any)")
        return

    tender.ai_executive_summary = ai_result.get("executive_summary")
    tender.ai_eligibility_summary = ai_result.get("eligibility_summary")
    tender.ai_risk_factors = ai_result.get("risk_factors")
    logger.info(f"[analyze] on-demand analysis complete for {tender.tender_number}")
