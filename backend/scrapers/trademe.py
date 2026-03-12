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
        search_term = " ".join(query.keywords[:3])
        encoded = search_term.replace(" ", "+")
        url = f"{self.base_url}/a/trade-me-motors/cars/search?search_string={encoded}"
        # Use general search endpoint
        url = f"{self.base_url}/a/search?search_string={encoded}&sort_order=ExpiryDesc"
        if query.max_price:
            url += f"&price_max={int(query.max_price)}"

        self.logger.info(f"TradeMe searching: {url}")
        html = await self._get_page_html(url, extra_wait_ms=1500)
        if not html:
            return results

        soup = BeautifulSoup(html, "lxml")
        items = soup.select("tm-search-results tme-card-listing, [data-testid='listing-card'], .tm-marketplace-search-card")
        
        if not items:
            items = soup.select("li[data-testid], div[class*='listing'], article[class*='listing']")
        
        if not items:
            items = soup.select("tm-marketplace-search-results tme-search-results-item")

        self.logger.info(f"TradeMe found {len(items)} raw items")

        for item in items[:20]:
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
                href = link_el.get("href", "")
                if href.startswith("/"):
                    item_url = self.base_url + href
                elif href.startswith("http"):
                    item_url = href
                else:
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

        self.logger.info(f"TradeMe returning {len(results)} normalized results")
        return results
