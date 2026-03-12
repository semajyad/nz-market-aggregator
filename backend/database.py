import logging
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set.")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _client


SCHEMA_SQL = """
-- Search queries table
CREATE TABLE IF NOT EXISTS search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_query TEXT NOT NULL,
    parsed_keywords TEXT[] DEFAULT '{}',
    max_price NUMERIC,
    min_specs TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    notify_telegram BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_run_at TIMESTAMPTZ
);

-- Found items table (deduplication via unique URL + query_id)
CREATE TABLE IF NOT EXISTS found_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    price NUMERIC,
    price_display TEXT,
    condition TEXT DEFAULT 'Unknown',
    platform TEXT NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    description TEXT,
    found_at TIMESTAMPTZ DEFAULT now(),
    notified BOOLEAN DEFAULT FALSE,
    UNIQUE(query_id, url)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_found_items_query_id ON found_items(query_id);
CREATE INDEX IF NOT EXISTS idx_found_items_url ON found_items(url);
"""


async def create_search_query(
    raw_query: str,
    keywords: List[str],
    max_price: Optional[float],
    min_specs: List[str],
    notify_telegram: bool = True,
) -> Dict[str, Any]:
    db = get_client()
    data = {
        "raw_query": raw_query,
        "parsed_keywords": keywords,
        "max_price": max_price,
        "min_specs": min_specs,
        "notify_telegram": notify_telegram,
    }
    result = db.table("search_queries").insert(data).execute()
    return result.data[0]


async def get_all_queries(active_only: bool = False) -> List[Dict[str, Any]]:
    db = get_client()
    query = db.table("search_queries").select("*").order("created_at", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    result = query.execute()
    return result.data


async def get_query_by_id(query_id: str) -> Optional[Dict[str, Any]]:
    db = get_client()
    result = db.table("search_queries").select("*").eq("id", query_id).execute()
    return result.data[0] if result.data else None


async def update_query_last_run(query_id: str) -> None:
    db = get_client()
    from datetime import datetime, timezone
    db.table("search_queries").update(
        {"last_run_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", query_id).execute()


async def deactivate_query(query_id: str) -> None:
    db = get_client()
    db.table("search_queries").update({"is_active": False}).eq("id", query_id).execute()


async def item_exists(query_id: str, url: str) -> bool:
    db = get_client()
    result = (
        db.table("found_items")
        .select("id")
        .eq("query_id", query_id)
        .eq("url", url)
        .execute()
    )
    return len(result.data) > 0


async def save_found_item(
    query_id: str,
    title: str,
    price: Optional[float],
    price_display: str,
    condition: str,
    platform: str,
    url: str,
    image_url: Optional[str] = None,
    description: Optional[str] = None,
    notified: bool = False,
) -> Optional[Dict[str, Any]]:
    db = get_client()
    data = {
        "query_id": query_id,
        "title": title,
        "price": price,
        "price_display": price_display,
        "condition": condition,
        "platform": platform,
        "url": url,
        "image_url": image_url,
        "description": description,
        "notified": notified,
    }
    try:
        result = db.table("found_items").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            logger.debug(f"Item already exists, skipping: {url}")
            return None
        logger.error(f"Error saving item: {e}")
        return None


async def get_items_for_query(
    query_id: str, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    db = get_client()
    result = (
        db.table("found_items")
        .select("*")
        .eq("query_id", query_id)
        .order("found_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


async def get_all_items(limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    db = get_client()
    result = (
        db.table("found_items")
        .select("*")
        .order("found_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


async def get_query_item_count(query_id: str) -> int:
    db = get_client()
    result = (
        db.table("found_items")
        .select("id", count="exact")
        .eq("query_id", query_id)
        .execute()
    )
    return result.count or 0
