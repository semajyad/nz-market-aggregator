import logging
from typing import List
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper
from models import NormalizedItem, ParsedQuery, Condition, Platform

logger = logging.getLogger(__name__)


class TrademeScraper(BaseScraper):
    platform_name = Platform.TRADEME
    base_url = "https://www.trademe.co.nz"
    rate_limit_seconds = 2.5

    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        results = []
        search_terms = self._build_search_terms(query, max_terms=3)

        for search_term in search_terms:
            encoded = search_term.replace(" ", "+")
            for page_num in (1, 2):
                url = (
                    f"{self.base_url}/a/search?search_string={encoded}"
                    f"&sort_order=ExpiryDesc&page={page_num}"
                )
                if query.max_price:
                    url += f"&price_max={int(query.max_price)}"

                self.logger.info(f"TradeMe searching: {url}")
                html = await self._get_page_html(url, extra_wait_ms=1500)
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")
                items = soup.select("tm-search-results tme-card-listing, [data-testid='listing-card'], .tm-marketplace-search-card")

                if not items:
                    items = soup.select("li[data-testid], div[class*='listing'], article[class*='listing']")

                if not items:
                    items = soup.select("tm-marketplace-search-results tme-search-results-item")

                self.logger.info(f"TradeMe found {len(items)} raw items for term '{search_term}' page {page_num}")

                for item in items[:80]:
                    try:
                        title_el = (
                            item.select_one("[data-testid='listing-title']")
                            or item.select_one(".tm-marketplace-search-card__title")
                            or item.select_one("h3")
                            or item.select_one("h2")
                            or item.select_one("[class*='title']")
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 3:
                            continue

                        price_el = (
                            item.select_one("[data-testid='price']")
                            or item.select_one(".tm-marketplace-search-card__price")
                            or item.select_one("[class*='price']")
                        )
                        price_text = price_el.get_text(strip=True) if price_el else "Price N/A"
                        price_val, price_display = self._clean_price(price_text)

                        if query.max_price and price_val and price_val > query.max_price:
                            continue

                        link_el = item.select_one("a[href]")
                        if not link_el:
                            continue
                        item_url = self._normalize_listing_url(link_el.get("href", ""))
                        if not item_url:
                            continue

                        img_el = item.select_one("img[src]")
                        image_url = img_el.get("src") if img_el else None

                        condition = Condition.USED
                        title_lower = title.lower()
                        if any(w in title_lower for w in ["brand new", "new in box", "unopened", "sealed"]):
                            condition = Condition.NEW

                        results.append(NormalizedItem(
                            title=self._truncate(title, 150),
                            price=price_val,
                            price_display=price_display,
                            condition=condition,
                            platform=self.platform_name,
                            url=item_url,
                            image_url=image_url,
                        ))
                    except Exception as e:
                        self.logger.debug(f"Error parsing TradeMe item: {e}")
                        continue

        deduped = self._dedupe_items_by_url(results)
        self.logger.info(f"TradeMe returning {len(deduped)} normalized results")
        return deduped[:100]
