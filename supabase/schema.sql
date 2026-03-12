-- ================================================================
-- NZ Market Aggregator - Supabase Schema
-- Run this ONCE in your Supabase project SQL editor.
-- Dashboard -> SQL Editor -> New Query -> Paste & Run
-- ================================================================

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

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_found_items_query_id ON found_items(query_id);
CREATE INDEX IF NOT EXISTS idx_found_items_found_at ON found_items(found_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_queries_is_active ON search_queries(is_active);

-- Disable Row Level Security for service-level access (anon key usage)
-- If you want to lock it down further, enable RLS and add policies.
ALTER TABLE search_queries DISABLE ROW LEVEL SECURITY;
ALTER TABLE found_items DISABLE ROW LEVEL SECURITY;
