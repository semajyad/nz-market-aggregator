import logging
import asyncio
import random
from typing import List
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper
from models import NormalizedItem, ParsedQuery, Condition, Platform

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    platform_name = Platform.FACEBOOK
    base_url = "https://www.facebook.com/marketplace"
    rate_limit_seconds = 4.0

    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        results = []
        search_terms = self._build_search_terms(query, max_terms=2)

        for search_term in search_terms:
            encoded = search_term.replace(" ", "%20")

            url = (
                f"https://www.facebook.com/marketplace/auckland/search"
                f"?query={encoded}&exact=false"
            )
            if query.max_price:
                url += f"&maxPrice={int(query.max_price)}"

            self.logger.info(f"Facebook Marketplace searching: {url}")

            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-blink-features=AutomationControlled",
                        ],
                    )
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                        viewport={"width": 1366, "height": 768},
                        locale="en-NZ",
                        timezone_id="Pacific/Auckland",
                    )
                    await context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['en-NZ', 'en'] });
                        window.chrome = { runtime: {} };
                    """)
                    page = await context.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(random.uniform(2, 4))

                    for _ in range(3):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(1.2)

                    html = await page.content()
                    await browser.close()

                soup = BeautifulSoup(html, "lxml")
                listing_items = soup.select("div[class*='x9f619'] a[href*='/marketplace/item/']")
                if not listing_items:
                    listing_items = soup.select("a[href*='/marketplace/item/']")

                for link in listing_items[:70]:
                    try:
                        href = link.get("href", "")
                        item_url = self._normalize_listing_url(href)
                        if not item_url:
                            continue

                        all_text = link.get_text(separator="\n", strip=True).split("\n")
                        all_text = [t for t in all_text if t and len(t) > 1]
                        if not all_text:
                            continue

                        title = None
                        price_text = None
                        for text in all_text:
                            if "$" in text and not price_text:
                                price_text = text
                            elif not title and len(text) > 4 and "$" not in text:
                                title = text
                        if not title:
                            title = all_text[0]

                        price_val, price_display = self._clean_price(price_text or "")
                        if query.max_price and price_val and price_val > query.max_price:
                            continue

                        img_el = link.select_one("img[src]")
                        image_url = img_el.get("src") if img_el else None

                        results.append(NormalizedItem(
                            title=self._truncate(title, 150),
                            price=price_val,
                            price_display=price_display if price_text else "See listing",
                            condition=Condition.USED,
                            platform=self.platform_name,
                            url=item_url,
                            image_url=image_url,
                        ))
                    except Exception as e:
                        self.logger.debug(f"Error parsing FB item: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Facebook Marketplace scraping error: {e}")

        deduped = self._dedupe_items_by_url(results)
        self.logger.info(f"Facebook Marketplace returning {len(deduped)} results")
        return deduped[:100]
