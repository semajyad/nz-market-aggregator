import asyncio
import logging
import random
from abc import ABC, abstractmethod
from urllib.parse import urljoin
from typing import List, Optional
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
