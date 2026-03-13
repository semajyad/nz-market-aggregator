import logging
import httpx
from typing import Optional
from models import NormalizedItem
from config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


async def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a raw message via Telegram Bot API."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured. Skipping notification.")
        return False

    url = TELEGRAM_API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendMessage")
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Telegram notification sent successfully.")
            return True
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = e.response.text
        except Exception:
            detail = "<unavailable>"
        logger.error(
            f"Failed to send Telegram notification: status={e.response.status_code}, "
            f"response={detail}"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


def _format_price(item: NormalizedItem) -> str:
    if item.price:
        return f"<b>💰 {item.price_display}</b>"
    return f"💰 {item.price_display}"


async def notify_new_item(item: NormalizedItem, query_raw: str) -> bool:
    """Send a formatted Telegram notification for a new found item."""
    platform_emoji = {
        "TradeMe": "🔵",
        "Facebook Marketplace": "🔷",
        "Cash Converters": "🟢",
        "PB Tech": "🔴",
        "Computer Lounge": "🟠",
        "Noel Leeming": "🟡",
        "MightyApe": "🦍",
    }
    emoji = platform_emoji.get(item.platform, "🛒")
    condition_tag = f"[{item.condition}]" if item.condition != "Unknown" else ""

    text = (
        f"🔔 <b>New Match Found!</b>\n\n"
        f"{emoji} <b>{item.platform}</b> {condition_tag}\n"
        f"📦 {item.title}\n"
        f"{_format_price(item)}\n"
        f"\n"
        f"🔍 <i>Query: {query_raw[:60]}{'...' if len(query_raw) > 60 else ''}</i>\n"
        f"\n"
        f"🔗 <a href=\"{item.url}\">View Listing</a>"
    )
    return await send_telegram_message(text)


async def notify_batch_summary(items_count: int, query_raw: str, platform_breakdown: dict) -> bool:
    """Send a summary when the hourly job finishes."""
    if items_count == 0:
        return True

    breakdown_lines = "\n".join(
        [f"  • {platform}: {count}" for platform, count in platform_breakdown.items() if count > 0]
    )
    text = (
        f"✅ <b>Scan Complete</b>\n\n"
        f"Found <b>{items_count} new item(s)</b>\n"
        f"🔍 <i>{query_raw[:60]}{'...' if len(query_raw) > 60 else ''}</i>\n\n"
        f"<b>By Platform:</b>\n{breakdown_lines}"
    )
    return await send_telegram_message(text)


async def notify_scan_error(query_raw: str, error: str) -> bool:
    """Send an error notification."""
    text = (
        f"⚠️ <b>Scan Error</b>\n\n"
        f"Query: <i>{query_raw[:60]}</i>\n"
        f"Error: <code>{error[:200]}</code>"
    )
    return await send_telegram_message(text)
