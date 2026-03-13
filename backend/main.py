import logging
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from models import (
    SearchQueryCreate,
    SearchQueryResponse,
    FoundItemResponse,
    RunNowRequest,
    TelegramTestRequest,
    ItemReviewUpdate,
)
import database
import nlp
import aggregator
import notifications

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_job():
    logger.info("Scheduler triggered: running all active queries...")
    await aggregator.run_all_active_queries()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NZ Market Aggregator backend...")
    scheduler.add_job(
        scheduled_job,
        trigger=IntervalTrigger(minutes=settings.SCRAPE_INTERVAL_MINUTES),
        id="hourly_aggregation",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started. Interval: every {settings.SCRAPE_INTERVAL_MINUTES} minutes.")
    yield
    scheduler.shutdown()
    logger.info("Scheduler shut down.")


app = FastAPI(
    title="NZ Market Aggregator API",
    description="Automated NZ second-hand and retail market monitor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Health Check ===

@app.get("/health")
async def health():
    return {"status": "ok", "service": "nz-market-aggregator"}


# === Queries ===

@app.post("/api/queries", response_model=SearchQueryResponse)
async def create_query(body: SearchQueryCreate, background_tasks: BackgroundTasks):
    """Create a new search query. Parses the natural language input with Gemini."""
    parsed = await nlp.parse_query(body.raw_query)
    query_row = await database.create_search_query(
        raw_query=body.raw_query,
        keywords=parsed.keywords,
        max_price=parsed.max_price,
        min_specs=parsed.min_specs,
        notify_telegram=body.notify_telegram,
    )
    count = await database.get_query_item_count(query_row["id"])

    # Immediately kick off a background scrape for new queries
    background_tasks.add_task(aggregator.run_aggregation_for_query, query_row["id"])

    return SearchQueryResponse(
        id=query_row["id"],
        raw_query=query_row["raw_query"],
        parsed_keywords=query_row.get("parsed_keywords", []),
        max_price=query_row.get("max_price"),
        min_specs=query_row.get("min_specs", []),
        is_active=query_row.get("is_active", True),
        notify_telegram=query_row.get("notify_telegram", True),
        created_at=query_row["created_at"],
        last_run_at=query_row.get("last_run_at"),
        total_results=count,
    )


@app.get("/api/queries", response_model=List[SearchQueryResponse])
async def list_queries(active_only: bool = Query(False)):
    """List all search queries."""
    rows = await database.get_all_queries(active_only=active_only)
    results = []
    for row in rows:
        count = await database.get_query_item_count(row["id"])
        results.append(SearchQueryResponse(
            id=row["id"],
            raw_query=row["raw_query"],
            parsed_keywords=row.get("parsed_keywords", []),
            max_price=row.get("max_price"),
            min_specs=row.get("min_specs", []),
            is_active=row.get("is_active", True),
            notify_telegram=row.get("notify_telegram", True),
            created_at=row["created_at"],
            last_run_at=row.get("last_run_at"),
            total_results=count,
        ))
    return results


@app.get("/api/queries/{query_id}", response_model=SearchQueryResponse)
async def get_query(query_id: str):
    """Get a single query by ID."""
    row = await database.get_query_by_id(query_id)
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")
    count = await database.get_query_item_count(query_id)
    return SearchQueryResponse(
        id=row["id"],
        raw_query=row["raw_query"],
        parsed_keywords=row.get("parsed_keywords", []),
        max_price=row.get("max_price"),
        min_specs=row.get("min_specs", []),
        is_active=row.get("is_active", True),
        notify_telegram=row.get("notify_telegram", True),
        created_at=row["created_at"],
        last_run_at=row.get("last_run_at"),
        total_results=count,
    )


@app.patch("/api/queries/{query_id}/pause")
async def pause_query(query_id: str):
    """Pause a search query (stops future scheduled runs)."""
    row = await database.get_query_by_id(query_id)
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")
    await database.deactivate_query(query_id)
    return {"success": True, "message": "Query paused."}


@app.patch("/api/queries/{query_id}/resume")
async def resume_query(query_id: str):
    """Resume a paused search query."""
    row = await database.get_query_by_id(query_id)
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")
    await database.resume_query(query_id)
    return {"success": True, "message": "Query resumed."}


@app.delete("/api/queries/{query_id}")
async def delete_query(query_id: str):
    """Delete a search query and all associated found items."""
    row = await database.get_query_by_id(query_id)
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")
    await database.delete_query(query_id)
    return {"success": True, "message": "Query deleted."}


# === Items ===

@app.get("/api/items", response_model=List[FoundItemResponse])
async def list_all_items(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List all found items across all queries."""
    rows = await database.get_all_items(limit=limit, offset=offset)
    return [_row_to_item_response(r) for r in rows]


@app.get("/api/queries/{query_id}/items", response_model=List[FoundItemResponse])
async def list_query_items(
    query_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List all found items for a specific query."""
    rows = await database.get_items_for_query(query_id, limit=limit, offset=offset)
    return [_row_to_item_response(r) for r in rows]


@app.patch("/api/items/{item_id}/review", response_model=FoundItemResponse)
async def mark_item_review(item_id: str, body: ItemReviewUpdate):
    row = await database.set_item_reviewed(item_id, body.reviewed)
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return _row_to_item_response(row)


@app.delete("/api/items/{item_id}")
async def delete_item(item_id: str):
    await database.delete_item(item_id)
    return {"success": True, "message": "Item removed."}


def _row_to_item_response(row: dict) -> FoundItemResponse:
    return FoundItemResponse(
        id=row["id"],
        query_id=row["query_id"],
        title=row["title"],
        price=row.get("price"),
        price_display=row.get("price_display", ""),
        condition=row.get("condition", "Unknown"),
        platform=row["platform"],
        url=row["url"],
        image_url=row.get("image_url"),
        description=row.get("description"),
        found_at=row["found_at"],
        notified=row.get("notified", False),
        reviewed=row.get("reviewed", False),
        reviewed_at=row.get("reviewed_at"),
    )


# === Manual Run ===

@app.post("/api/run-now")
async def run_now(body: RunNowRequest, background_tasks: BackgroundTasks):
    """Manually trigger the aggregation engine for a specific query."""
    row = await database.get_query_by_id(body.query_id)
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")
    background_tasks.add_task(aggregator.run_aggregation_for_query, body.query_id)
    return {"success": True, "message": "Aggregation started in background."}


@app.post("/api/run-all")
async def run_all(background_tasks: BackgroundTasks):
    """Manually trigger the aggregation engine for all active queries."""
    background_tasks.add_task(aggregator.run_all_active_queries)
    return {"success": True, "message": "Full aggregation started in background."}


# === Notifications ===

@app.post("/api/notifications/test")
async def test_notification(body: TelegramTestRequest):
    """Send a test Telegram notification."""
    success = await notifications.send_telegram_message(body.message)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to send Telegram notification. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
        )
    return {"success": True, "message": "Telegram notification sent."}


# === Scheduler Info ===

@app.get("/api/scheduler/status")
async def scheduler_status():
    """Get current scheduler status."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
            "trigger": str(job.trigger),
        })
    return {
        "running": scheduler.running,
        "jobs": jobs,
        "interval_minutes": settings.SCRAPE_INTERVAL_MINUTES,
    }
