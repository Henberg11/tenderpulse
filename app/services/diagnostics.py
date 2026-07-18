"""
Turns a crawl failure into a plain-English explanation plus a ready-to-copy
technical block, so someone who isn't a programmer can forward it and get help
without needing to read logs or interpret error codes themselves.
"""
from dataclasses import dataclass

from app.models import CrawlRun, CrawlRunStatus

KNOWN_ERROR_PATTERNS: list[tuple[str, str]] = [
    ("captcha", "The government website is showing a CAPTCHA (a 'prove you're human' test), which is blocking automatic checking."),
    ("timeout", "The government website took too long to respond, or the crawler is having trouble finding something on the page that used to be there."),
    ("net::err", "The crawler couldn't reach the government website at all -- it may be down, or blocking access."),
    ("connection refused", "The government website (or our own database) refused the connection -- could be a temporary outage."),
    ("waiting for selector", "The government website's page layout appears to have changed, so the crawler can no longer find the information it's looking for."),
    ("locator", "The government website's page layout appears to have changed, so the crawler can no longer find the information it's looking for."),
    ("403", "The government website blocked the request (access denied) -- it may have detected automated browsing."),
    ("429", "The government website is rate-limiting us -- we're checking too often and it's temporarily refusing requests."),
    ("database", "There's a problem with our own database, not the government website. This is an internal issue."),
]

GENERIC_CAUSE = "The exact cause isn't automatically recognized -- this needs a developer to look at the technical details below."


@dataclass
class Diagnosis:
    plain_english_summary: str
    likely_cause: str
    technical_block: str


def diagnose_failure(portal: str, recent_runs: list[CrawlRun]) -> Diagnosis:
    last_run = recent_runs[0]
    error_text = (last_run.error_message or "").lower()

    likely_cause = GENERIC_CAUSE
    for pattern, explanation in KNOWN_ERROR_PATTERNS:
        if pattern in error_text:
            likely_cause = explanation
            break

    if last_run.status == CrawlRunStatus.FAILED:
        summary = f"TenderPulse's {portal.upper()} checker has been failing and needs attention."
    else:
        summary = f"TenderPulse's {portal.upper()} checker is running but hasn't found any results in a while, which usually means it's broken silently."
        if likely_cause == GENERIC_CAUSE:
            likely_cause = "The government website's page layout probably changed, so the crawler is looking in the wrong place and finding nothing (without technically 'erroring')."

    technical_block = _build_technical_block(portal, recent_runs)

    return Diagnosis(plain_english_summary=summary, likely_cause=likely_cause, technical_block=technical_block)


def _build_technical_block(portal: str, recent_runs: list[CrawlRun]) -> str:
    lines = [
        "--- TECHNICAL DETAILS (copy everything below this line to your AI CTO) ---",
        f"Portal: {portal}",
        f"Most recent run: {recent_runs[0].started_at.isoformat()}",
        f"Most recent status: {recent_runs[0].status.value}",
        f"Most recent error: {recent_runs[0].error_message or '(no error message -- ran but found 0 results)'}",
        "",
        "Last 5 run history (newest first):",
    ]
    for r in recent_runs[:5]:
        lines.append(
            f"  - {r.started_at.isoformat()} | status={r.status.value} | "
            f"listings_found={r.listings_found} | tenders_created={r.tenders_created}"
        )
    return "\n".join(lines)
