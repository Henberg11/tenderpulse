"""
Every crawler (GeM, CPPP, state portals, PSUs, ...) implements this interface.
This is what makes "add a new portal without changing the architecture"
actually true.
"""
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

from playwright.async_api import async_playwright, Page


@dataclass
class RawTenderListing:
    tender_number: str
    title: str
    portal_url: str
    reference_number: str | None = None
    organisation_name: str | None = None
    estimated_value: float | None = None
    emd_amount: float | None = None
    bid_submission_end: datetime | None = None
    location: str | None = None
    document_urls: list[str] = field(default_factory=list)
    raw_fields: dict = field(default_factory=dict)


@asynccontextmanager
async def browser_page():
    """One browser, one page, shared across an entire crawl run (searching
    every keyword AND downloading every matched document). An earlier
    version launched a brand-new Chromium process per document download --
    on a slow disk that's a real, avoidable cost multiplied by however many
    tenders matched. Every crawler should wrap its whole run in this once,
    not launch its own browser per method call."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            yield page
        finally:
            await browser.close()


class BaseCrawler(ABC):
    portal_name: str

    @abstractmethod
    async def search(self, page: Page, keywords: list[str]) -> list[RawTenderListing]:
        raise NotImplementedError

    @abstractmethod
    async def download_documents(self, page: Page, listing: RawTenderListing, dest_dir: str) -> list[str]:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True
