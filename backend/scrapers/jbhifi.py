import logging
import json
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from typing import List
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper
from models import NormalizedItem, ParsedQuery, Condition, Platform

logger = logging.getLogger(__name__)


class JBHifiScraper(BaseScraper):
    platform_name = Platform.JB_HIFI
    base_url = "https://www.jbhifi.co.nz"
    rate_limit_seconds = 2.0

    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        results = []
        search_terms = self._build_search_terms(query, max_terms=3)

        for search_term in search_terms:
            encoded = search_term.replace(" ", "+")
            candidate_urls = [
                f"{self.base_url}/search?q={encoded}",
                f"{self.base_url}/search?query={encoded}",
                f"{self.base_url}/search?text={encoded}",
            ]

            for url in candidate_urls:
                self.logger.info(f"JB Hi-Fi searching: {url}")
                html = await self._get_page_html(url, extra_wait_ms=1600)
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")
                items = (
                    soup.select("[data-testid='product-grid-item']")
                    or soup.select(".product-tile")
                    or soup.select(".product-card")
                    or soup.select("article[class*='product']")
                    or soup.select("[class*='product-item']")
                )

                self.logger.info(f"JB Hi-Fi found {len(items)} raw items for term '{search_term}'")

                for item in items[:80]:
                    try:
                        title_el = (
                            item.select_one("[data-testid='product-title']")
                            or item.select_one(".product-title")
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
                            item.select_one("[data-testid='price']")
                            or item.select_one(".price")
                            or item.select_one("[class*='price']")
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
                        self.logger.debug(f"Error parsing JB Hi-Fi item: {e}")
                        continue

                for product in self._extract_products_from_json_ld(soup)[:80]:
                    title = (product.get("title") or "").strip()
                    item_url = self._normalize_listing_url(product.get("href", ""))
                    if not title or not item_url:
                        continue
                    price_val = product.get("price")
                    if query.max_price and price_val and price_val > query.max_price:
                        continue
                    results.append(NormalizedItem(
                        title=self._truncate(title, 150),
                        price=price_val,
                        price_display=product.get("price_display") or "See listing",
                        condition=Condition.NEW,
                        platform=self.platform_name,
                        url=item_url,
                        image_url=product.get("image_url"),
                    ))

                suggest_url = (
                    f"{self.base_url}/search/suggest.json?q={quote_plus(search_term)}"
                    "&resources[type]=product&resources[limit]=25"
                    "&resources[options][fields]=title,product_type,variants.title,vendor,tag"
                )
                try:
                    req = Request(
                        suggest_url,
                        headers={
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "application/json",
                        },
                    )
                    with urlopen(req, timeout=12) as resp:
                        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    products = (
                        payload.get("resources", {})
                        .get("results", {})
                        .get("products", [])
                    )
                    for product in products:
                        title = (product.get("title") or "").strip()
                        item_url = self._normalize_listing_url(product.get("url", ""))
                        if not title or not item_url:
                            continue
                        price_val = None
                        price_display = "See listing"
                        if product.get("price"):
                            price_val, price_display = self._clean_price(str(product.get("price")))
                        if query.max_price and price_val and price_val > query.max_price:
                            continue
                        results.append(NormalizedItem(
                            title=self._truncate(title, 150),
                            price=price_val,
                            price_display=price_display,
                            condition=Condition.NEW,
                            platform=self.platform_name,
                            url=item_url,
                            image_url=product.get("image"),
                        ))
                except Exception as e:
                    self.logger.debug(f"JB Hi-Fi suggest fallback failed: {e}")

        deduped = self._dedupe_items_by_url(results)
        self.logger.info(f"JB Hi-Fi returning {len(deduped)} results")
        return deduped[:100]
