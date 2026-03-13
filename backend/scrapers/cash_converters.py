import logging
from typing import List
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper
from models import NormalizedItem, ParsedQuery, Condition, Platform

logger = logging.getLogger(__name__)


class CashConvertersScraper(BaseScraper):
    platform_name = Platform.CASH_CONVERTERS
    base_url = "https://www.cashconverters.co.nz"
    rate_limit_seconds = 2.0

    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        results = []
        search_term = " ".join(query.keywords[:3])
        encoded = search_term.replace(" ", "+")
        url = f"{self.base_url}/search?q={encoded}"

        self.logger.info(f"Cash Converters searching: {url}")
        html = await self._get_page_html(url, extra_wait_ms=1000)
        if not html:
            return results

        soup = BeautifulSoup(html, "lxml")

        # Cash Converters product grid items
        items = (
            soup.select(".product-item")
            or soup.select(".product-card")
            or soup.select("[class*='product']")
            or soup.select("li.grid__item")
            or soup.select(".grid-product")
        )

        self.logger.info(f"Cash Converters found {len(items)} raw items")

        for item in items[:20]:
            try:
                title_el = (
                    item.select_one(".product-item__title")
                    or item.select_one(".grid-product__title")
                    or item.select_one("h2")
                    or item.select_one("h3")
                    or item.select_one("[class*='title']")
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title:
                    continue

                price_el = (
                    item.select_one(".product-item__price")
                    or item.select_one(".grid-product__price")
                    or item.select_one("[class*='price']")
                    or item.select_one(".price")
                )
                price_text = price_el.get_text(strip=True) if price_el else ""
                price_val, price_display = self._clean_price(price_text)

                if query.max_price and price_val and price_val > query.max_price:
                    continue

                link_el = item.select_one("a[href]")
                if not link_el:
                    continue
                href = link_el.get("href", "")
                item_url = self._normalize_listing_url(href)
                if not item_url:
                    continue

                img_el = item.select_one("img[src], img[data-src]")
                image_url = None
                if img_el:
                    image_url = img_el.get("src") or img_el.get("data-src")
                    if image_url and image_url.startswith("//"):
                        image_url = "https:" + image_url

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
                self.logger.debug(f"Error parsing Cash Converters item: {e}")
                continue

        self.logger.info(f"Cash Converters returning {len(results)} results")
        return results
