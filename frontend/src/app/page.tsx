'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Search, Bell, RefreshCw, Trash2, ExternalLink, CheckCircle2,
  XCircle, Clock, Package, ChevronDown, ChevronUp, Zap, BellRing,
  LayoutDashboard, ListFilter, Plus, Activity,
} from 'lucide-react'
import { api, SearchQuery, FoundItem } from '@/lib/api'
import { formatDistanceToNow, format } from 'date-fns'

const PLATFORM_COLORS: Record<string, string> = {
  'TradeMe': 'bg-blue-100 text-blue-800',
  'Facebook Marketplace': 'bg-indigo-100 text-indigo-800',
  'Cash Converters': 'bg-green-100 text-green-800',
  'PB Tech': 'bg-red-100 text-red-800',
  'Computer Lounge': 'bg-orange-100 text-orange-800',
  'Noel Leeming': 'bg-yellow-100 text-yellow-800',
  'MightyApe': 'bg-purple-100 text-purple-800',
}

const CONDITION_COLORS: Record<string, string> = {
  'New': 'bg-emerald-100 text-emerald-700',
  'Used': 'bg-amber-100 text-amber-700',
  'Unknown': 'bg-gray-100 text-gray-600',
}

function PlatformBadge({ platform }: { platform: string }) {
  const cls = PLATFORM_COLORS[platform] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {platform}
    </span>
  )
}

function ConditionBadge({ condition }: { condition: string }) {
  const cls = CONDITION_COLORS[condition] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {condition}
    </span>
  )
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${active ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
  )
}

function ItemCard({ item }: { item: FoundItem }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow flex gap-3">
      {item.image_url && (
        <div className="flex-shrink-0 w-16 h-16 rounded-md overflow-hidden bg-gray-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={item.image_url}
            alt={item.title}
            className="w-full h-full object-cover"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-gray-900 line-clamp-2 flex-1">{item.title}</p>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 text-blue-600 hover:text-blue-800"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <span className="text-sm font-bold text-gray-900">{item.price_display || 'N/A'}</span>
          <PlatformBadge platform={item.platform} />
          <ConditionBadge condition={item.condition} />
          {item.notified && (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600">
              <Bell className="w-3 h-3" /> Notified
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-gray-400">
          Found {formatDistanceToNow(new Date(item.found_at), { addSuffix: true })}
        </p>
      </div>
    </div>
  )
}

function QueryCard({
  query,
  isSelected,
  onSelect,
  onRunNow,
  onDeactivate,
}: {
  query: SearchQuery
  isSelected: boolean
  onSelect: () => void
  onRunNow: (id: string) => void
  onDeactivate: (id: string) => void
}) {
  return (
    <div
      className={`rounded-lg border p-4 cursor-pointer transition-all ${
        isSelected
          ? 'border-blue-500 bg-blue-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-sm'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <StatusDot active={query.is_active} />
          <p className="text-sm font-medium text-gray-900 truncate">{query.raw_query}</p>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onRunNow(query.id)}
            title="Run now"
            className="p-1.5 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          {query.is_active && (
            <button
              onClick={() => onDeactivate(query.id)}
              title="Pause"
              className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1">
        {query.parsed_keywords.slice(0, 4).map((kw) => (
          <span key={kw} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
            {kw}
          </span>
        ))}
        {query.parsed_keywords.length > 4 && (
          <span className="px-1.5 py-0.5 bg-gray-100 text-gray-500 text-xs rounded">
            +{query.parsed_keywords.length - 4} more
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <Package className="w-3 h-3" />
          {query.total_results} items found
        </span>
        {query.max_price && (
          <span className="font-medium text-green-700">Max ${query.max_price}</span>
        )}
        {query.last_run_at ? (
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDistanceToNow(new Date(query.last_run_at), { addSuffix: true })}
          </span>
        ) : (
          <span className="text-gray-300">Never run</span>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [queries, setQueries] = useState<SearchQuery[]>([])
  const [items, setItems] = useState<FoundItem[]>([])
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null)
  const [rawQuery, setRawQuery] = useState('')
  const [notifyTelegram, setNotifyTelegram] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [isRunningAll, setIsRunningAll] = useState(false)
  const [isLoadingItems, setIsLoadingItems] = useState(false)
  const [runningQueryIds, setRunningQueryIds] = useState<Set<string>>(new Set())
  const [activeTab, setActiveTab] = useState<'feed' | 'monitors'>('monitors')
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null)
  const [apiStatus, setApiStatus] = useState<'ok' | 'error' | 'checking'>('checking')
  const [scheduleInfo, setScheduleInfo] = useState<string>('')

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const loadQueries = useCallback(async () => {
    try {
      const data = await api.listQueries()
      setQueries(data)
    } catch {
      /* silent */
    }
  }, [])

  const loadItems = useCallback(async (queryId?: string) => {
    setIsLoadingItems(true)
    try {
      const data = queryId
        ? await api.listQueryItems(queryId)
        : await api.listAllItems()
      setItems(data)
    } catch {
      setItems([])
    } finally {
      setIsLoadingItems(false)
    }
  }, [])

  const checkHealth = useCallback(async () => {
    try {
      await api.health()
      setApiStatus('ok')
      const status = await api.schedulerStatus()
      if (status.jobs.length > 0) {
        const nextRun = status.jobs[0].next_run
        const nextDate = new Date(nextRun.replace(' ', 'T').split('+')[0])
        setScheduleInfo(`Next scan ${formatDistanceToNow(nextDate, { addSuffix: true })}`)
      }
    } catch {
      setApiStatus('error')
    }
  }, [])

  useEffect(() => {
    checkHealth()
    loadQueries()
  }, [checkHealth, loadQueries])

  useEffect(() => {
    loadItems(selectedQueryId ?? undefined)
  }, [selectedQueryId, loadItems])

  const handleCreateQuery = async () => {
    if (!rawQuery.trim()) return
    setIsCreating(true)
    try {
      const newQuery = await api.createQuery({ raw_query: rawQuery.trim(), notify_telegram: notifyTelegram })
      setQueries((prev) => [newQuery, ...prev])
      setRawQuery('')
      showToast('Monitor created! First scan running in background.', 'success')
      setSelectedQueryId(newQuery.id)
      setActiveTab('feed')
      setTimeout(loadQueries, 5000)
    } catch (e) {
      showToast(`Failed: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
    } finally {
      setIsCreating(false)
    }
  }

  const handleRunNow = async (queryId: string) => {
    setRunningQueryIds((prev) => new Set(prev).add(queryId))
    try {
      await api.runNow(queryId)
      showToast('Scan started in background!', 'success')
      setTimeout(() => {
        loadQueries()
        loadItems(selectedQueryId ?? undefined)
        setRunningQueryIds((prev) => {
          const next = new Set(prev)
          next.delete(queryId)
          return next
        })
      }, 8000)
    } catch (e) {
      showToast(`Failed: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
      setRunningQueryIds((prev) => {
        const next = new Set(prev)
        next.delete(queryId)
        return next
      })
    }
  }

  const handleRunAll = async () => {
    setIsRunningAll(true)
    try {
      await api.runAll()
      showToast('Full scan started for all monitors!', 'success')
      setTimeout(() => {
        loadQueries()
        loadItems()
        setIsRunningAll(false)
      }, 10000)
    } catch (e) {
      showToast(`Failed: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
      setIsRunningAll(false)
    }
  }

  const handleDeactivate = async (queryId: string) => {
    if (!confirm('Pause this monitor? It will stop running in future scans.')) return
    try {
      await api.deactivateQuery(queryId)
      showToast('Monitor paused.', 'success')
      loadQueries()
      if (selectedQueryId === queryId) setSelectedQueryId(null)
    } catch {
      showToast('Failed to pause monitor.', 'error')
    }
  }

  const handleTestNotification = async () => {
    try {
      await api.testNotification()
      showToast('✅ Telegram test sent! Check your phone.', 'success')
    } catch {
      showToast('❌ Telegram test failed. Check your bot token and chat ID.', 'error')
    }
  }

  const activeQueries = queries.filter((q) => q.is_active)
  const pausedQueries = queries.filter((q) => !q.is_active)
  const totalItems = queries.reduce((sum, q) => sum + q.total_results, 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <Search className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900">NZ Market Aggregator</h1>
              <p className="text-xs text-gray-500">Automated NZ deal finder</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {scheduleInfo && (
              <span className="hidden sm:flex items-center gap-1 text-xs text-gray-500">
                <Activity className="w-3 h-3" />
                {scheduleInfo}
              </span>
            )}
            <div className="flex items-center gap-1.5 text-xs">
              {apiStatus === 'ok' ? (
                <><span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" /><span className="text-green-700">API Online</span></>
              ) : apiStatus === 'error' ? (
                <><span className="w-2 h-2 rounded-full bg-red-500" /><span className="text-red-700">API Offline</span></>
              ) : (
                <><span className="w-2 h-2 rounded-full bg-gray-300 animate-pulse" /><span className="text-gray-500">Connecting...</span></>
              )}
            </div>
            <button
              onClick={handleTestNotification}
              className="flex items-center gap-1 px-2 py-1.5 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
              title="Send a test Telegram notification"
            >
              <BellRing className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Test Alert</span>
            </button>
            <button
              onClick={handleRunAll}
              disabled={isRunningAll || activeQueries.length === 0}
              className="flex items-center gap-1 px-2 py-1.5 text-xs rounded-md bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRunningAll ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">{isRunningAll ? 'Scanning...' : 'Scan All'}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{activeQueries.length}</p>
            <p className="text-xs text-gray-500 mt-0.5">Active Monitors</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-bold text-green-600">{totalItems.toLocaleString()}</p>
            <p className="text-xs text-gray-500 mt-0.5">Total Deals Found</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-bold text-purple-600">7</p>
            <p className="text-xs text-gray-500 mt-0.5">Platforms Monitored</p>
          </div>
        </div>

        {/* New Query Input */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Plus className="w-4 h-4 text-blue-600" />
            Create New Monitor
          </h2>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={rawQuery}
                onChange={(e) => setRawQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !isCreating && handleCreateQuery()}
                placeholder="e.g. Computer that can run Docker, 50 Chrome tabs, budget $1000"
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <button
              onClick={handleCreateQuery}
              disabled={isCreating || !rawQuery.trim()}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {isCreating ? (
                <><RefreshCw className="w-4 h-4 animate-spin" />Parsing...</>
              ) : (
                <><Zap className="w-4 h-4" />Start Monitor</>
              )}
            </button>
          </div>
          <div className="mt-3 flex items-center gap-4">
            <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyTelegram}
                onChange={(e) => setNotifyTelegram(e.target.checked)}
                className="w-3.5 h-3.5 rounded text-blue-600"
              />
              <Bell className="w-3.5 h-3.5" />
              Send Telegram notifications
            </label>
            <div className="flex flex-wrap gap-1">
              {['laptop under $800', 'iPhone 14 under $500', 'PS5 under $400'].map((ex) => (
                <button
                  key={ex}
                  onClick={() => setRawQuery(ex)}
                  className="px-2 py-0.5 text-xs bg-gray-100 hover:bg-blue-50 hover:text-blue-700 text-gray-600 rounded transition-colors"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tab layout */}
        <div className="flex gap-1 mb-4">
          <button
            onClick={() => setActiveTab('monitors')}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'monitors'
                ? 'bg-white text-blue-700 border border-gray-200 shadow-sm'
                : 'text-gray-600 hover:bg-white hover:text-gray-900'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            Monitors
            {queries.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
                {queries.length}
              </span>
            )}
          </button>
          <button
            onClick={() => { setActiveTab('feed'); setSelectedQueryId(null) }}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'feed'
                ? 'bg-white text-blue-700 border border-gray-200 shadow-sm'
                : 'text-gray-600 hover:bg-white hover:text-gray-900'
            }`}
          >
            <ListFilter className="w-4 h-4" />
            All Deals Feed
            {totalItems > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-green-100 text-green-700">
                {totalItems}
              </span>
            )}
          </button>
        </div>

        {activeTab === 'monitors' && (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Queries list */}
            <div className="lg:col-span-2 space-y-3">
              {activeQueries.length === 0 && pausedQueries.length === 0 ? (
                <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
                  <Search className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No monitors yet.</p>
                  <p className="text-gray-400 text-xs mt-1">Create your first one above.</p>
                </div>
              ) : (
                <>
                  {activeQueries.map((q) => (
                    <QueryCard
                      key={q.id}
                      query={q}
                      isSelected={selectedQueryId === q.id}
                      onSelect={() => {
                        setSelectedQueryId(q.id)
                        loadItems(q.id)
                      }}
                      onRunNow={handleRunNow}
                      onDeactivate={handleDeactivate}
                    />
                  ))}
                  {pausedQueries.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 px-1 mb-2">Paused</p>
                      {pausedQueries.map((q) => (
                        <QueryCard
                          key={q.id}
                          query={q}
                          isSelected={selectedQueryId === q.id}
                          onSelect={() => {
                            setSelectedQueryId(q.id)
                            loadItems(q.id)
                          }}
                          onRunNow={handleRunNow}
                          onDeactivate={handleDeactivate}
                        />
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Items panel */}
            <div className="lg:col-span-3">
              {selectedQueryId ? (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Results for: <span className="text-blue-600">{queries.find(q => q.id === selectedQueryId)?.raw_query}</span>
                    </h3>
                    <button
                      onClick={() => handleRunNow(selectedQueryId)}
                      disabled={runningQueryIds.has(selectedQueryId)}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-md transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3 h-3 ${runningQueryIds.has(selectedQueryId) ? 'animate-spin' : ''}`} />
                      {runningQueryIds.has(selectedQueryId) ? 'Scanning...' : 'Refresh'}
                    </button>
                  </div>
                  {isLoadingItems ? (
                    <div className="space-y-3">
                      {[1, 2, 3].map((i) => (
                        <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                          <div className="h-3 bg-gray-100 rounded w-1/2" />
                        </div>
                      ))}
                    </div>
                  ) : items.length === 0 ? (
                    <div className="bg-white rounded-lg border border-dashed border-gray-300 p-8 text-center">
                      <Package className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                      <p className="text-gray-500 text-sm">No items found yet.</p>
                      <p className="text-gray-400 text-xs mt-1">Click Refresh to run a manual scan.</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[600px] overflow-y-auto scrollbar-thin pr-1">
                      {items.map((item) => <ItemCard key={item.id} item={item} />)}
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 text-center h-full flex flex-col items-center justify-center">
                  <LayoutDashboard className="w-10 h-10 text-gray-300 mb-3" />
                  <p className="text-gray-500 text-sm">Select a monitor to view its results</p>
                  <p className="text-gray-400 text-xs mt-1">Or switch to the All Deals Feed tab</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'feed' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-900">
                All Deals Feed
                {items.length > 0 && <span className="ml-2 text-gray-400 font-normal">({items.length} items)</span>}
              </h3>
              <button
                onClick={() => loadItems()}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors"
              >
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>
            {isLoadingItems ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                    <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                    <div className="h-3 bg-gray-100 rounded w-1/2" />
                  </div>
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
                <Package className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No deals found yet.</p>
                <p className="text-gray-400 text-sm mt-1">Create a monitor above and run a scan to populate the feed.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {items.map((item) => <ItemCard key={item.id} item={item} />)}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Platforms footer */}
      <footer className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <p className="text-xs text-gray-400 text-center">
          Monitoring: TradeMe · Facebook Marketplace · Cash Converters · PB Tech · Computer Lounge · Noel Leeming · MightyApe
        </p>
      </footer>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all ${
          toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
        }`}>
          {toast.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          ) : (
            <XCircle className="w-4 h-4 flex-shrink-0" />
          )}
          {toast.msg}
        </div>
      )}
    </div>
  )
}
