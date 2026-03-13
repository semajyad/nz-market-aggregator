import asyncio
import logging
import random
import json
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlencode, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from models import NormalizedItem, ParsedQuery

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


class BaseScraper(ABC):
    platform_name: str = "Unknown"
    base_url: str = ""
    rate_limit_seconds: float = 2.0
    blocked_link_tokens: tuple[str, ...] = (
        "/cart",
        "cart?",
        "checkout",
        "basket",
        "addtocart",
        "add-to-cart",
        "buy-now",
    )

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def search(self, query: ParsedQuery) -> List[NormalizedItem]:
        pass

    async def _get_page_html(self, url: str, wait_selector: Optional[str] = None, extra_wait_ms: int = 0) -> Optional[str]:
        """Fetch page HTML using Playwright with stealth settings."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--disable-gpu",
                    ],
                )
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1366, "height": 768},
                    locale="en-NZ",
                    timezone_id="Pacific/Auckland",
                    extra_http_headers={
                        "Accept-Language": "en-NZ,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    },
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                    window.chrome = { runtime: {} };
                """)
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=10000)
                    except Exception:
                        self.logger.debug(f"Wait selector '{wait_selector}' not found on {url}")

                if extra_wait_ms > 0:
                    await asyncio.sleep(extra_wait_ms / 1000)

                html = await page.content()
                await browser.close()
                await asyncio.sleep(self.rate_limit_seconds + random.uniform(0.5, 1.5))
                return html
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    def _clean_price(self, price_str: str) -> tuple[Optional[float], str]:
        """Parse price string to (float_value, display_string)."""
        if not price_str:
            return None, "Price N/A"
        import re
        price_str = price_str.strip()
        display = price_str
        numeric = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
        if numeric:
            try:
                return float(numeric), display
            except ValueError:
                pass
        return None, display

    def _truncate(self, text: str, max_len: int = 200) -> str:
        return text[:max_len].strip() if text else ""

    def _is_valid_listing_href(self, href: str) -> bool:
        if not href:
            return False
        value = href.strip().lower()
        if value.startswith("javascript:") or value.startswith("#"):
            return False
        return not any(token in value for token in self.blocked_link_tokens)

    def _normalize_listing_url(self, href: str) -> Optional[str]:
        if not self._is_valid_listing_href(href):
            return None
        return urljoin(self.base_url, href.strip())

    def _build_search_terms(self, query: ParsedQuery, max_terms: int = 4) -> List[str]:
        cleaned_keywords: List[str] = []
        for kw in query.keywords:
            value = (kw or "").strip()
            if len(value) >= 2:
                cleaned_keywords.append(value)
        if not cleaned_keywords:
            return [query.raw_query.strip()] if query.raw_query.strip() else []

        candidates: List[str] = []
        candidates.append(" ".join(cleaned_keywords[:4]))
        candidates.append(" ".join(cleaned_keywords[:3]))
        candidates.append(" ".join(cleaned_keywords[:2]))
        candidates.extend(cleaned_keywords[:2])

        deduped: List[str] = []
        for candidate in candidates:
            value = candidate.strip()
            if value and value not in deduped:
                deduped.append(value)
            if len(deduped) >= max_terms:
                break
        return deduped

    def _dedupe_items_by_url(self, items: List[NormalizedItem]) -> List[NormalizedItem]:
        deduped: List[NormalizedItem] = []
        seen_urls = set()
        for item in items:
            normalized_url = (item.url or "").strip().lower()
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            deduped.append(item)
        return deduped

    def _extract_products_from_json_ld(self, soup: Any) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        scripts = soup.select("script[type='application/ld+json']")
        if not scripts:
            return products

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
                return
            if not isinstance(node, dict):
                return

            node_type = node.get("@type")
            if isinstance(node_type, list):
                node_type = node_type[0] if node_type else None

            if node_type == "ListItem" and isinstance(node.get("item"), dict):
                walk(node.get("item"))

            if node_type == "Product":
                title = (node.get("name") or "").strip()
                href = (node.get("url") or "").strip()
                image = node.get("image")
                if isinstance(image, list):
                    image = image[0] if image else None
                offers = node.get("offers")
                if isinstance(offers, list):
                    offers = offers[0] if offers else None
                price = None
                price_display = "See listing"
                if isinstance(offers, dict):
                    raw_price = offers.get("price")
                    try:
                        if raw_price is not None:
                            price = float(str(raw_price))
                            price_display = f"${price:.2f}"
                    except Exception:
                        price = None
                products.append({
                    "title": title,
                    "href": href,
                    "price": price,
                    "price_display": price_display,
                    "image_url": image if isinstance(image, str) else None,
                })

            for value in node.values():
                walk(value)

        for script in scripts:
            raw = (script.string or script.get_text() or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            walk(data)

        return products

    def _fallback_links_from_duckduckgo(self, domain: str, search_term: str, max_links: int = 20) -> List[str]:
        query = f"site:{domain} {search_term}"
        url = "https://duckduckgo.com/html/?" + urlencode({"q": query})
        links: List[str] = []
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "text/html",
                },
            )
            with urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            self.logger.debug(f"DuckDuckGo fallback failed for {domain}: {e}")
            return links

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        anchors = soup.select("a.result__a, a[data-testid='result-title-a'], a[href]")
        seen = set()
        for anchor in anchors:
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            if "duckduckgo.com/l/?" in href and "uddg=" in href:
                try:
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    href = unquote((qs.get("uddg") or [""])[0])
                except Exception:
                    continue
            if domain not in href.lower():
                continue
            normalized = self._normalize_listing_url(href)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            links.append(normalized)
            if len(links) >= max_links:
                break
        if links:
            return links

        bing_url = "https://www.bing.com/search?" + urlencode({"q": query})
        try:
            req = Request(
                bing_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "text/html",
                },
            )
            with urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            self.logger.debug(f"Bing fallback failed for {domain}: {e}")
            return links

        soup = BeautifulSoup(html, "lxml")
        anchors = soup.select("li.b_algo h2 a, a[href]")
        seen = set()
        for anchor in anchors:
            href = (anchor.get("href") or "").strip()
            if not href or domain not in href.lower():
                continue
            normalized = self._normalize_listing_url(href)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            links.append(normalized)
            if len(links) >= max_links:
                break
        return links
