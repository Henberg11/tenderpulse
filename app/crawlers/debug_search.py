"""
One-off debug script: searches GeM for "uniform" and saves a screenshot plus
the raw page HTML, so we can see exactly what the crawler sees instead of
guessing why the count doesn't match a real browser session.

Run: docker compose exec api python -m app.crawlers.debug_search

Output appears in the top-level `debug/` folder -- it'll show up directly in
your local project folder too, since that folder is synced with the
container automatically.
"""
import asyncio
import os

from playwright.async_api import async_playwright

from app.config import settings


async def main():
    os.makedirs("debug", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Explicit larger viewport -- rules out the page switching to a
        # cut-down mobile/responsive layout that shows fewer results.
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})

        await page.goto(f"{settings.gem_base_url}/all-bids", wait_until="networkidle")

        search_box = page.locator("input#searchBid")
        await search_box.fill("uniform")
        await search_box.press("Enter")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        await page.screenshot(path="debug/search_result.png", full_page=True)
        html = await page.content()
        with open("debug/search_result.html", "w", encoding="utf-8") as f:
            f.write(html)

        count = await page.locator("div.bids").count()
        print(f"div.bids count: {count}")
        print(f"Current URL: {page.url}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
