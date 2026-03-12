const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010'

export interface SearchQuery {
  id: string
  raw_query: string
  parsed_keywords: string[]
  max_price: number | null
  min_specs: string[]
  is_active: boolean
  notify_telegram: boolean
  created_at: string
  last_run_at: string | null
  total_results: number
}

export interface FoundItem {
  id: string
  query_id: string
  title: string
  price: number | null
  price_display: string
  condition: string
  platform: string
  url: string
  image_url: string | null
  description: string | null
  found_at: string
  notified: boolean
}

export interface CreateQueryPayload {
  raw_query: string
  notify_telegram: boolean
}

export interface SchedulerStatus {
  running: boolean
  jobs: { id: string; next_run: string; trigger: string }[]
  interval_minutes: number
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  createQuery: (payload: CreateQueryPayload) =>
    request<SearchQuery>('/api/queries', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listQueries: (activeOnly = false) =>
    request<SearchQuery[]>(`/api/queries?active_only=${activeOnly}`),

  getQuery: (id: string) => request<SearchQuery>(`/api/queries/${id}`),

  deactivateQuery: (id: string) =>
    request<{ success: boolean }>(`/api/queries/${id}`, { method: 'DELETE' }),

  listAllItems: (limit = 200, offset = 0) =>
    request<FoundItem[]>(`/api/items?limit=${limit}&offset=${offset}`),

  listQueryItems: (queryId: string, limit = 100) =>
    request<FoundItem[]>(`/api/queries/${queryId}/items?limit=${limit}`),

  runNow: (queryId: string) =>
    request<{ success: boolean }>('/api/run-now', {
      method: 'POST',
      body: JSON.stringify({ query_id: queryId }),
    }),

  runAll: () =>
    request<{ success: boolean }>('/api/run-all', { method: 'POST' }),

  testNotification: (message?: string) =>
    request<{ success: boolean }>('/api/notifications/test', {
      method: 'POST',
      body: JSON.stringify({ message: message ?? 'Test from NZ Market Aggregator! 🎉' }),
    }),

  schedulerStatus: () => request<SchedulerStatus>('/api/scheduler/status'),

  health: () => request<{ status: string }>('/health'),
}
