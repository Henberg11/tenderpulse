"""
The digest email. Fires automatically right after each crawl finishes
(chained from crawl_tasks.py, not on its own fixed schedule) -- this means
it never fires before real data is actually ready, and naturally happens up
to twice a day, matching the 9 AM / 4:30 PM crawl schedule.

Deliberately silent on quiet runs: if nothing genuinely new was found since
the previous crawl, no email gets sent at all. The person explicitly asked
for this -- an email that shows up even on empty days trains you to ignore
it, defeating the whole point.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.database import celery_db_session
from app.models import CrawlRun, CrawlRunStatus, PortalSource, Tender, Corrigendum
from app.services.notifications import send_html_email
from app.tasks.celery_app import celery_app

# A tender doesn't need to be brand new to deserve a mention -- if it's
# closing very soon, that's worth surfacing in the digest even if it was
# actually found in an earlier crawl and just hasn't closed yet.
CLOSING_SOON_DAYS = 3


@celery_app.task(name="app.tasks.digest_tasks.send_digest")
def send_digest():
    asyncio.run(_send_digest_async())


async def _send_digest_async():
    async with celery_db_session() as db:
        cutoff = await _get_previous_crawl_cutoff(db)
        if cutoff is None:
            logger.info("[digest] no previous completed crawl to compare against yet, skipping this time")
            return

        new_matches = await _get_new_core_matches(db, cutoff)
        corrigenda = await _get_recent_corrigenda(db, cutoff)

        if not new_matches and not corrigenda:
            logger.info("[digest] nothing new since the last crawl -- skipping, no email sent")
            return

        closing_soon = await _get_closing_soon(db)

        subject = _build_subject(new_matches, corrigenda)
        html = _build_html(new_matches, corrigenda, closing_soon)
        plain = _build_plain(new_matches, corrigenda, closing_soon)

        send_html_email(subject, html, plain)


async def _get_previous_crawl_cutoff(db) -> datetime | None:
    """The digest compares against the crawl BEFORE the one that just
    finished (which triggered this task) -- not the one that just
    finished itself, since that would compare a run against its own
    results."""
    result = await db.execute(
        select(CrawlRun)
        .where(CrawlRun.portal == PortalSource.GEM.value)
        .where(CrawlRun.status.in_([CrawlRunStatus.SUCCESS, CrawlRunStatus.PARTIAL]))
        .order_by(desc(CrawlRun.started_at))
        .limit(2)
    )
    runs = result.scalars().all()
    if len(runs) < 2:
        return None  # this was the first-ever successful crawl, nothing to compare against
    return runs[1].finished_at


async def _get_new_core_matches(db, cutoff: datetime) -> list[Tender]:
    result = await db.execute(
        select(Tender)
        .options(selectinload(Tender.organisation))
        .where(Tender.portal_source == PortalSource.GEM)
        .where(Tender.created_at > cutoff)
        .order_by(Tender.bid_submission_end.asc().nullslast())
    )
    tenders = result.scalars().all()
    return [t for t in tenders if t.matched_keywords]


async def _get_recent_corrigenda(db, cutoff: datetime) -> list[Corrigendum]:
    result = await db.execute(
        select(Corrigendum)
        .options(selectinload(Corrigendum.tender))
        .where(Corrigendum.detected_at > cutoff)
        .order_by(desc(Corrigendum.detected_at))
    )
    return list(result.scalars().all())


async def _get_closing_soon(db) -> list[Tender]:
    now = datetime.now(timezone.utc)
    threshold = now + timedelta(days=CLOSING_SOON_DAYS)
    result = await db.execute(
        select(Tender)
        .options(selectinload(Tender.organisation))
        .where(Tender.bid_submission_end.isnot(None))
        .where(Tender.bid_submission_end >= now)
        .where(Tender.bid_submission_end <= threshold)
        .order_by(Tender.bid_submission_end.asc())
    )
    tenders = result.scalars().all()
    return [t for t in tenders if t.matched_keywords]


def _build_subject(new_matches: list[Tender], corrigenda: list[Corrigendum]) -> str:
    parts = []
    if new_matches:
        parts.append(f"{len(new_matches)} new match{'es' if len(new_matches) != 1 else ''}")
    if corrigenda:
        parts.append(f"{len(corrigenda)} change{'s' if len(corrigenda) != 1 else ''}")
    today = datetime.now(timezone.utc).strftime("%a, %b %d")
    return f"TenderPulse: {' · '.join(parts)} · {today}"


def _days_left(bid_submission_end: datetime | None) -> str:
    if not bid_submission_end:
        return ""
    # Calendar-date difference, not a raw timedelta -- confirmed via direct
    # testing that timedelta.days truncates and undercounts by one whenever
    # the deadline's time-of-day doesn't exactly match "now" (which is
    # essentially always the case). A tender closing 2 calendar days from
    # now was showing "1 day left".
    today = datetime.now(timezone.utc).date()
    deadline_date = bid_submission_end.date()
    days = (deadline_date - today).days
    if days < 0:
        return "closed"
    if days == 0:
        return "today"
    return f"{days} day{'s' if days != 1 else ''}"


def _build_plain(new_matches: list[Tender], corrigenda: list[Corrigendum], closing_soon: list[Tender]) -> str:
    lines = ["TenderPulse update", ""]
    if new_matches:
        lines.append(f"NEW MATCHES ({len(new_matches)})")
        for t in new_matches:
            org = t.organisation.name if t.organisation else "Unknown organisation"
            lines.append(f"- {t.title[:80]} -- {org} -- {_days_left(t.bid_submission_end)} left")
        lines.append("")
    if corrigenda:
        lines.append(f"CHANGES DETECTED ({len(corrigenda)})")
        for c in corrigenda:
            title = c.tender.title[:80] if c.tender else "Unknown tender"
            lines.append(f"- {title}: {c.field_changed} changed")
        lines.append("")
    if closing_soon:
        lines.append(f"CLOSING SOON ({len(closing_soon)})")
        for t in closing_soon:
            lines.append(f"- {t.title[:80]} -- {_days_left(t.bid_submission_end)} left")
    return "\n".join(lines)


def _build_html(new_matches: list[Tender], corrigenda: list[Corrigendum], closing_soon: list[Tender]) -> str:
    # Email clients (Gmail, Outlook) don't reliably support CSS variables or
    # <style> blocks -- everything here is inline styles with hardcoded
    # colors, deliberately simpler markup than the web dashboard.
    def tender_row(t: Tender, accent: str) -> str:
        org = t.organisation.name if t.organisation else ""
        days = _days_left(t.bid_submission_end)
        return f"""
        <div style="border-left: 3px solid {accent}; padding: 10px 14px; margin-bottom: 8px; background: #f7f7f8;">
          <div style="display: flex; justify-content: space-between; gap: 8px; font-size: 14px; font-weight: 600; color: #1a1a1a;">
            <span>{_escape(t.title[:90])}</span>
            <span style="color: {accent}; white-space: nowrap;">{days}</span>
          </div>
          <div style="font-size: 12px; color: #666; margin-top: 4px;">{_escape(org)} &middot; {_escape(t.tender_number)}</div>
        </div>"""

    def corrigendum_row(c: Corrigendum) -> str:
        title = c.tender.title[:90] if c.tender else "Unknown tender"
        return f"""
        <div style="padding: 8px 0; border-bottom: 1px solid #e5e5e5; font-size: 13px;">
          <div style="font-weight: 600; color: #1a1a1a;">{_escape(title)}</div>
          <div style="color: #666; margin-top: 2px;">{_escape(c.field_changed)} changed</div>
        </div>"""

    sections = ""
    if new_matches:
        sections += f"""
        <div style="font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.03em; margin: 20px 0 8px;">New matches ({len(new_matches)})</div>
        {''.join(tender_row(t, "#2f6fe0") for t in new_matches)}"""
    if corrigenda:
        sections += f"""
        <div style="font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.03em; margin: 20px 0 8px;">Changes detected ({len(corrigenda)})</div>
        {''.join(corrigendum_row(c) for c in corrigenda)}"""
    if closing_soon:
        sections += f"""
        <div style="font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.03em; margin: 20px 0 8px;">Closing soon ({len(closing_soon)})</div>
        {''.join(tender_row(t, "#d64545") for t in closing_soon)}"""

    return f"""
    <div style="max-width: 560px; margin: 0 auto; font-family: -apple-system, Arial, sans-serif;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
        <div style="width: 8px; height: 8px; border-radius: 50%; background: #1e9e6b;"></div>
        <span style="font-weight: 600; font-size: 16px; color: #1a1a1a;">TenderPulse</span>
      </div>
      {sections}
      <p style="font-size: 11px; color: #999; text-align: center; margin: 24px 0 0;">Sent automatically by your TenderPulse system.</p>
    </div>"""


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
