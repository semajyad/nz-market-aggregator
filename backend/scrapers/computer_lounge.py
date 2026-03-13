import logging
from typing import List
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper
from models import NormalizedItem, ParsedQuery, Condition, Platform

logger = logging.getLogger(__name__)


class ComputerLoungeScraper(BaseScraper):
    platform_name = Platform.COMPUTER_LOUNGE
    base_url = "https://www.computerlounge.co.nz"
    rate_limit_seconds = 2.0

    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        results = []
        search_terms = self._build_search_terms(query, max_terms=3)

        for search_term in search_terms:
            encoded = search_term.replace(" ", "+")
            candidate_urls = [
                f"{self.base_url}/components/search.asp?search={encoded}",
                f"{self.base_url}/search?search={encoded}",
                f"{self.base_url}/search?q={encoded}",
            ]

            for url in candidate_urls:
                self.logger.info(f"Computer Lounge searching: {url}")
                html = await self._get_page_html(url, extra_wait_ms=1200)
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")
                items = (
                    soup.select(".product-block")
                    or soup.select(".cl-product")
                    or soup.select("[class*='product']")
                    or soup.select("div.item")
                )

                self.logger.info(f"Computer Lounge found {len(items)} raw items for term '{search_term}'")

                for item in items[:70]:
                    try:
                        title_el = (
                            item.select_one(".product-title")
                            or item.select_one("h2")
                            or item.select_one("h3")
                            or item.select_one("[class*='title']")
                            or item.select_one("[class*='name']")
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title:
                            continue

                        price_el = (
                            item.select_one(".price")
                            or item.select_one("[class*='price']")
                        )
                        price_text = price_el.get_text(strip=True) if price_el else ""
                        price_val, price_display = self._clean_price(price_text)

                        if query.max_price and price_val and price_val > query.max_price:
                            continue

                        link_el = (
                            item.select_one(".product-title a[href]")
                            or item.select_one("h2 a[href]")
                            or item.select_one("h3 a[href]")
                            or item.select_one("a[href*='/product']")
                            or item.select_one("a[href*='/products']")
                        )

                        if not link_el or not self._is_valid_listing_href(link_el.get("href", "")):
                            valid_links = [
                                a.get("href", "")
                                for a in item.select("a[href]")
                                if self._is_valid_listing_href(a.get("href", ""))
                            ]
                            href = valid_links[0] if valid_links else ""
                        else:
                            href = link_el.get("href", "")

                        if not href:
                            continue
                        item_url = self._normalize_listing_url(href)
                        if not item_url:
                            continue

                        img_el = item.select_one("img[src], img[data-src], img[data-lazy-src]")
                        image_url = None
                        if img_el:
                            image_url = img_el.get("src") or img_el.get("data-src") or img_el.get("data-lazy-src")
                            if image_url and image_url.startswith("//"):
                                image_url = "https:" + image_url

                        results.append(NormalizedItem(
                            title=self._truncate(title, 150),
                            price=price_val,
                            price_display=price_display if price_text else "See listing",
                            condition=Condition.NEW,
                            platform=self.platform_name,
                            url=item_url,
                            image_url=image_url,
                        ))
                    except Exception as e:
                        self.logger.debug(f"Error parsing Computer Lounge item: {e}")
                        continue

        deduped = self._dedupe_items_by_url(results)
        self.logger.info(f"Computer Lounge returning {len(deduped)} results")
        return deduped[:90]
