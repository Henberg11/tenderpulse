"""
GeM (Government e-Marketplace) crawler -- Phase 1 target portal.

Selectors below were confirmed against the live site on 2026-07-16 by
inspecting real search results for the keyword "uniform". GeM's markup could
change at any time (see docs/AUTONOMY.md on selector drift) -- if the
watchdog reports zero results for several runs, that's the first place to
re-check.

Confirmed structure of one result card:
  div.bids                                   <- one tender, repeated per result
    div.block_header
      p.bid_no
        a.bid_no_hover[href]                 <- bid number text + document download link
    div.card-body
      ...
        a[data-content]                      <- FULL untruncated tender title
                                                 (the visible text is truncated with "...",
                                                 data-content has the real thing)

Confirmed: search box is input#searchBid (plain text input, press Enter to search).

IMPORTANT: GeM's search matches individual words, not phrases -- see
app/utils/keywords.py for why GEM_SEARCH_TERMS (broad, single words) is
separate from SCHOOL_UNIFORM_KEYWORDS (precise phrases used to filter
results afterward).

PERFORMANCE NOTE: search() and download_documents() both take an already-open
`page` rather than managing their own browser -- callers should wrap a whole
crawl run in `app.crawlers.base.browser_page()` once and reuse that same page
throughout, rather than launching a new browser per method call (an earlier
version did this per-document, which meant launching Chromium a dozen+ times
per crawl cycle).
"""
import asyncio
import hashlib
import os
import re
from datetime import datetime

from loguru import logger
from playwright.async_api import Page
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.crawlers.base import BaseCrawler, RawTenderListing, browser_page


class GemCrawler(BaseCrawler):
    portal_name = "gem"

    # How many result pages to read per keyword (10 results/page on GeM).
    # A single common word can have 60+ total results nationwide -- reading
    # only page 1 (confirmed via direct comparison against a competitor's
    # results) meant seeing whichever 10 tenders anywhere in India happened
    # to close soonest, which could easily push genuine Gujarat tenders off
    # the visible page entirely. 5 pages = up to 50 results/keyword, a
    # balance between real coverage and not hammering GeM/taking forever.
    MAX_PAGES_PER_KEYWORD = 5

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.gem_base_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    async def search(self, page: Page, keywords: list[str]) -> list[RawTenderListing]:
        results: list[RawTenderListing] = []

        for keyword in keywords:
            logger.info(f"[GeM] searching keyword: {keyword}")
            results.extend(await self._search_single_keyword(page, keyword))

        deduped: dict[str, RawTenderListing] = {}
        for r in results:
            if r.tender_number in deduped:
                continue
            deduped[r.tender_number] = r

        logger.info(f"[GeM] found {len(deduped)} unique tenders across {len(keywords)} keywords")
        return list(deduped.values())

    async def _search_single_keyword(self, page: Page, keyword: str) -> list[RawTenderListing]:
        """Confirmed via a direct, real comparison against a competitor's
        results (TenderJeeto) that NOT paginating was the single biggest
        cause of missed tenders -- worse than any keyword gap. GeM's
        results for a single word like "uniform" can span 60+ results
        across 7+ pages, sorted oldest-deadline-first ACROSS ALL OF INDIA,
        not filtered to Gujarat. Reading only page 1 meant we were seeing
        whichever 10 tenders (from any state) happened to close soonest
        nationwide -- a real Gujarat tender with a slightly later deadline
        could easily be pushed off that first page entirely by unrelated
        tenders from other states. This walks forward through multiple
        pages per keyword to see a real slice of the results, not just
        whatever happened to load first."""
        listings: list[RawTenderListing] = []

        search_url = f"{self.base_url}/all-bids"
        await page.goto(search_url, wait_until="networkidle")

        search_box = page.locator("input#searchBid")
        await search_box.fill(keyword)
        await search_box.press("Enter")
        await page.wait_for_load_state("networkidle")

        for page_num in range(1, self.MAX_PAGES_PER_KEYWORD + 1):
            cards = page.locator("div.bids div.card")
            count = await self._wait_for_stable_result_count(page, cards)
            logger.info(f"[GeM] '{keyword}' page {page_num}: {count} result cards")

            for i in range(count):
                listing = await self._parse_one_card(page, cards.nth(i), keyword)
                if listing:
                    listings.append(listing)

            if count == 0:
                break  # nothing on this page at all -- definitely the end

            advanced = await self._go_to_next_page(page)
            if not advanced:
                logger.info(f"[GeM] '{keyword}': no more pages after page {page_num}")
                break

        return listings

    async def _go_to_next_page(self, page: Page) -> bool:
        """Clicks GeM's pagination "Next" control if one exists and is
        usable. Returns False (safe to stop) if there's no next page, or if
        anything about this goes wrong -- pagination failing should never
        crash the whole keyword's results, just stop collecting more of
        them for this keyword."""
        try:
            next_link = page.locator("a:has-text('Next'), li:has-text('Next') a").first
            if await next_link.count() == 0:
                return False
            classes = await next_link.evaluate("el => el.closest('li') ? el.closest('li').className : ''")
            if classes and ("disabled" in classes.lower()):
                return False
            await next_link.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(500)
            return True
        except Exception as e:
            logger.warning(f"[GeM] couldn't advance to next page (stopping here, not a crash): {e}")
            return False

    async def _parse_one_card(self, page: Page, card, keyword: str) -> RawTenderListing | None:
        try:
            bid_link = card.locator("a.bid_no_hover").first
            tender_number = (await bid_link.inner_text()).strip()
            href = await bid_link.get_attribute("href") or ""
            portal_url = href if href.startswith("http") else f"{self.base_url}{href}"

            # The visible title text is truncated with "..."; the full
            # title lives in the data-content attribute of the same link
            # (it's a Bootstrap popover).
            #
            # Short timeout (4s, not Playwright's 30s default) on
            # purpose: a small number of cards use a different layout
            # (visible in real testing as "RA NO:" reverse-auction-linked
            # bids alongside the normal "BID NO:" ones) where this
            # selector doesn't match at all. Confirmed via this
            # session's actual logs -- these were costing a full 30
            # seconds of wasted waiting *per occurrence, every single
            # crawl* before this fix. Fully supporting that card
            # variant's real structure still needs a live inspection
            # session (same process as the original selectors) -- this
            # fix doesn't recover those tenders, it just stops them from
            # being expensive to skip.
            title_link = card.locator("a[data-content]").first
            title = await title_link.get_attribute("data-content", timeout=4000)
            if not title:
                title = (await title_link.inner_text(timeout=4000)).strip()

            # No single stable selector was confirmed for the organisation
            # name field, so we parse it from the card's plain text instead
            # of a fragile nested class chain -- more resilient to minor
            # markup changes.
            card_text = await card.inner_text()
            org_name = self._extract_after_label(card_text, "Department Name And Address:")

            # EMD and estimated value are NOT shown on the search results
            # page -- they only exist inside the full tender PDF (see
            # Phase 2: document intelligence). The deadline IS shown here
            # though, so we capture that now.
            end_date_text = self._extract_line_after_label(card_text, "End Date:")
            bid_submission_end = self._parse_gem_datetime(end_date_text)

            return RawTenderListing(
                tender_number=tender_number,
                title=title.strip(),
                portal_url=portal_url,
                organisation_name=org_name,
                bid_submission_end=bid_submission_end,
                raw_fields={"matched_keyword": keyword},
            )
        except Exception as e:
            logger.warning(f"[GeM] failed to parse a result card: {e}")

    @staticmethod
    async def _wait_for_stable_result_count(page: Page, cards_locator, max_wait_seconds: float = 8.0) -> int:
        """GeM's results render client-side after the network goes idle, and
        they don't all appear at once -- a fixed sleep undercounted real
        results (confirmed: found 1 of 10+ actual cards on a real search).
        Poll until the count stops changing between checks, instead of
        guessing a delay."""
        previous_count = -1
        stable_checks = 0
        elapsed = 0.0
        interval = 0.5

        while elapsed < max_wait_seconds:
            current_count = await cards_locator.count()
            if current_count == previous_count and current_count > 0:
                stable_checks += 1
                if stable_checks >= 2:  # unchanged across two checks in a row = settled
                    return current_count
            else:
                stable_checks = 0
            previous_count = current_count
            await page.wait_for_timeout(int(interval * 1000))
            elapsed += interval

        return previous_count  # give up and use whatever we last saw

    @staticmethod
    def _extract_after_label(text: str, label: str) -> str | None:
        """Pull the line(s) immediately following a label like 'Department
        Name And Address:' out of a card's plain-text dump."""
        match = re.search(re.escape(label) + r"\s*\n?(.+?)(?:\n\n|\nStart Date:|\Z)", text, re.DOTALL)
        if not match:
            return None
        return " ".join(match.group(1).split())[:500]

    @staticmethod
    def _extract_line_after_label(text: str, label: str) -> str | None:
        """Pull just the single line of text following a label like
        'End Date:' -- for one-value fields, unlike the multi-line
        organisation address."""
        match = re.search(re.escape(label) + r"\s*(.+)", text)
        if not match:
            return None
        return match.group(1).split("\n")[0].strip()

    @staticmethod
    def _parse_gem_datetime(text: str | None) -> datetime | None:
        """GeM shows dates like '16-07-2026 8:00 PM'. Returns None (rather
        than raising) on anything unexpected -- a missing/odd date shouldn't
        break ingestion of an otherwise-good tender."""
        if not text:
            return None
        try:
            return datetime.strptime(text.strip(), "%d-%m-%Y %I:%M %p")
        except ValueError:
            logger.warning(f"[GeM] couldn't parse date: {text!r}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    async def download_documents(self, page: Page, listing: RawTenderListing, dest_dir: str) -> list[str]:
        """The bid-number link IS the document download link on GeM (confirmed:
        href="/showbidDocument/<id>" triggers a direct PDF download) -- no
        separate document-links page to navigate to."""
        os.makedirs(dest_dir, exist_ok=True)
        downloaded_paths: list[str] = []

        async with page.expect_download() as download_info:
            try:
                await page.goto(listing.portal_url)
            except Exception:
                # GeM's bid-number links trigger an immediate file download
                # rather than a normal page load. Playwright treats that as
                # an aborted navigation and page.goto() throws
                # net::ERR_ABORTED -- but the download itself still
                # completes. Only the goto() call is expected to fail here;
                # if the download genuinely didn't happen, the next line
                # (awaiting download_info.value) will raise its own timeout
                # error, which we don't swallow.
                pass
        download = await download_info.value

        tmp_path = os.path.join(dest_dir, download.suggested_filename)
        await download.save_as(tmp_path)

        content_hash = self._hash_file(tmp_path)
        final_path = os.path.join(dest_dir, f"{content_hash}_{download.suggested_filename}")
        if not os.path.exists(final_path):
            os.rename(tmp_path, final_path)
        else:
            os.remove(tmp_path)

        downloaded_paths.append(final_path)
        return downloaded_paths

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]


if __name__ == "__main__":
    from app.utils.keywords import GEM_SEARCH_TERMS

    async def _main():
        crawler = GemCrawler()
        async with browser_page() as page:
            listings = await crawler.search(page, GEM_SEARCH_TERMS[:1])  # just "uniform" for the smoke test
            for l in listings:
                print(f"{l.tender_number} | {l.title[:80]} | {l.organisation_name}")

    asyncio.run(_main())
