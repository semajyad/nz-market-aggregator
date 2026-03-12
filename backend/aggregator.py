import asyncio
import logging
from typing import List, Dict
from models import NormalizedItem, ParsedQuery
from scrapers import (
    TrademeScraper,
    CashConvertersScraper,
    PBTechScraper,
    ComputerLoungeScraper,
    NoelLeemingScraper,
    MightyApeScraper,
    FacebookScraper,
)
import database
import notifications

logger = logging.getLogger(__name__)


async def _run_scraper_safe(scraper, query: ParsedQuery) -> List[NormalizedItem]:
    """Run a single scraper and return empty list on error."""
    try:
        return await scraper.search(query)
    except Exception as e:
        logger.error(f"Scraper {scraper.platform_name} failed: {e}")
        return []


async def run_aggregation_for_query(query_id: str) -> Dict:
    """
    Full aggregation pipeline for a single search query:
    1. Load query from DB
    2. Run all scrapers concurrently (with semaphore to limit concurrency)
    3. Deduplicate against DB
    4. Save new items
    5. Send notifications for new items
    6. Return summary
    """
    query_row = await database.get_query_by_id(query_id)
    if not query_row:
        logger.error(f"Query {query_id} not found in database.")
        return {"error": "Query not found"}

    parsed_query = ParsedQuery(
        keywords=query_row.get("parsed_keywords", []),
        max_price=query_row.get("max_price"),
        min_specs=query_row.get("min_specs", []),
        raw_query=query_row.get("raw_query", ""),
    )

    logger.info(f"Starting aggregation for query: '{parsed_query.raw_query}' | keywords: {parsed_query.keywords}")

    # Initialize all scrapers
    scrapers = [
        TrademeScraper(),
        CashConvertersScraper(),
        PBTechScraper(),
        ComputerLoungeScraper(),
        NoelLeemingScraper(),
        MightyApeScraper(),
        FacebookScraper(),
    ]

    # Run scrapers with limited concurrency (max 3 at a time to avoid IP bans)
    semaphore = asyncio.Semaphore(3)

    async def bounded_scrape(scraper):
        async with semaphore:
            return await _run_scraper_safe(scraper, parsed_query)

    scraper_results = await asyncio.gather(*[bounded_scrape(s) for s in scrapers])

    # Flatten all results
    all_items: List[NormalizedItem] = []
    for items in scraper_results:
        all_items.extend(items)

    logger.info(f"Total raw items collected: {len(all_items)}")

    # Deduplicate and save new items
    new_items: List[NormalizedItem] = []
    platform_breakdown: Dict[str, int] = {}

    for item in all_items:
        try:
            exists = await database.item_exists(query_id, item.url)
            if not exists:
                saved = await database.save_found_item(
                    query_id=query_id,
                    title=item.title,
                    price=item.price,
                    price_display=item.price_display,
                    condition=item.condition.value if hasattr(item.condition, 'value') else str(item.condition),
                    platform=item.platform.value if hasattr(item.platform, 'value') else str(item.platform),
                    url=item.url,
                    image_url=item.image_url,
                    description=item.description,
                    notified=False,
                )
                if saved:
                    new_items.append(item)
                    platform = item.platform.value if hasattr(item.platform, 'value') else str(item.platform)
                    platform_breakdown[platform] = platform_breakdown.get(platform, 0) + 1
        except Exception as e:
            logger.error(f"Error processing item '{item.title}': {e}")

    logger.info(f"New items to notify: {len(new_items)}")

    # Send notifications if enabled
    should_notify = query_row.get("notify_telegram", True)
    if should_notify and new_items:
        # Send individual notifications for each new item (with rate limiting)
        for item in new_items:
            await notifications.notify_new_item(item, parsed_query.raw_query)
            await asyncio.sleep(0.5)  # Rate limit Telegram messages

    # Update last run timestamp
    await database.update_query_last_run(query_id)

    summary = {
        "query_id": query_id,
        "raw_query": parsed_query.raw_query,
        "total_scraped": len(all_items),
        "new_items": len(new_items),
        "platform_breakdown": platform_breakdown,
    }
    logger.info(f"Aggregation complete: {summary}")
    return summary


async def run_all_active_queries() -> List[Dict]:
    """Run aggregation for ALL active queries. Called by the hourly scheduler."""
    logger.info("=== Hourly aggregation run starting ===")
    active_queries = await database.get_all_queries(active_only=True)

    if not active_queries:
        logger.info("No active queries to process.")
        return []

    summaries = []
    for q in active_queries:
        try:
            summary = await run_aggregation_for_query(q["id"])
            summaries.append(summary)
            # Small pause between queries to be respectful to scraped sites
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error running query {q['id']}: {e}")
            summaries.append({"query_id": q["id"], "error": str(e)})

    logger.info(f"=== Hourly run complete. Processed {len(summaries)} queries ===")
    return summaries
