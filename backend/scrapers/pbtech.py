import logging
from typing import List
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper
from models import NormalizedItem, ParsedQuery, Condition, Platform

logger = logging.getLogger(__name__)


class PBTechScraper(BaseScraper):
    platform_name = Platform.PBTECH
    base_url = "https://www.pbtech.co.nz"
    rate_limit_seconds = 2.0

    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        results = []
        search_terms = self._build_search_terms(query, max_terms=3)

        for search_term in search_terms:
            encoded = search_term.replace(" ", "+")
            candidate_urls = [
                f"{self.base_url}/search?q={encoded}",
                f"{self.base_url}/search?sf={encoded}",
            ]
            for url in candidate_urls:
                self.logger.info(f"PB Tech searching: {url}")
                html = await self._get_page_html(url, extra_wait_ms=1200)
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")
                items = (
                    soup.select(".pbtech-prod-details-block")
                    or soup.select(".product-list-item")
                    or soup.select("[class*='product-item']")
                    or soup.select("[data-product-id]")
                    or soup.select(".itemblock")
                    or soup.select(".rec_browsed .swiper-slide")
                )
                self.logger.info(f"PB Tech found {len(items)} raw items for term '{search_term}'")

                for item in items[:60]:
                    try:
                        title_el = (
                            item.select_one(".pbtech-prod-name")
                            or item.select_one(".product-title-height p")
                            or item.select_one(".product-title-height a")
                            or item.select_one("h2")
                            or item.select_one("h3")
                            or item.select_one("[class*='name']")
                            or item.select_one("[class*='title']")
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title:
                            continue

                        price_el = (
                            item.select_one(".price-wrapper")
                            or item.select_one(".pbtech-price")
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
                        item_url = self._normalize_listing_url(link_el.get("href", ""))
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
                            condition=Condition.NEW,
                            platform=self.platform_name,
                            url=item_url,
                            image_url=image_url,
                        ))
                    except Exception as e:
                        self.logger.debug(f"Error parsing PB Tech item: {e}")
                        continue

            fallback_links = self._fallback_links_from_duckduckgo("pbtech.co.nz", search_term, max_links=20)
            for link in fallback_links:
                results.append(NormalizedItem(
                    title=self._truncate(f"PB Tech - {search_term}", 150),
                    price=None,
                    price_display="See listing",
                    condition=Condition.NEW,
                    platform=self.platform_name,
                    url=link,
                    image_url=None,
                ))

        deduped = self._dedupe_items_by_url(results)
        self.logger.info(f"PB Tech returning {len(deduped)} results")
        return deduped[:80]
