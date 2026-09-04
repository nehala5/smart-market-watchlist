import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api.js'
import { trafficLight, STATUS_META, freshnessLabel, ALERT_LABELS } from './types.js'
import { saveSnapshot, loadSnapshot, computeDeltas } from './offline.js'
import Header from './components/Header.jsx'
import MacroBanner from './components/MacroBanner.jsx'
import AlertPanel from './components/AlertPanel.jsx'
import WatchlistView from './components/WatchlistView.jsx'
import WatchlistManager from './components/WatchlistManager.jsx'
import HeatmapView from './components/HeatmapView.jsx'
import BacktestView from './components/BacktestView.jsx'
import ExplainTooltip from './components/ExplainTooltip.jsx'

export default function App() {
  const [dashboard, setDashboard] = useState(null)
  const [cached, setCached] = useState(null)
  const [deltas, setDeltas] = useState(null)
  const [view, setView] = useState('watchlist') // watchlist | heatmap | backtest
  const [filters, setFilters] = useState({})
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('sw-theme') || 'dark')
  const prevRef = useRef(null)
  const esRef = useRef(null)

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem('sw-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  // Initial load: show cached instantly, then fetch live
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const snap = await loadSnapshot()
      if (!cancelled && snap) {
        setCached(snap)
        prevRef.current = snap
      }
    })()
    return () => { cancelled = true }
  }, [])

  // Apply a fresh snapshot: compute deltas vs previous, cache it
  const applySnapshot = useMemo(() => (snap, isLive = true) => {
    setDashboard(snap)
    if (isLive) saveSnapshot(snap)
    const prev = prevRef.current
    if (prev && snap?.watchlist?.length) {
      setDeltas(computeDeltas(prev, snap))
    }
    if (isLive) prevRef.current = snap
  }, [])

  // Poll + SSE
  useEffect(() => {
    let stop = false
    async function poll() {
      try {
        const snap = await api.dashboard()
        if (!stop) applySnapshot(snap, true)
        setConnected(true)
        setError(null)
      } catch (e) {
        if (!stop) { setConnected(false); setError('Backend offline — showing cached data') }
      }
    }
    poll()
    const iv = setInterval(poll, 8000)
    // SSE enhancement
    let es
    try {
      es = new EventSource('/api/stream')
      es.onmessage = (ev) => {
        if (stop) return
        try { applySnapshot(JSON.parse(ev.data), true); setConnected(true); setError(null) }
        catch (_) {}
      }
      es.onerror = () => setConnected(false)
      esRef.current = es
    } catch (_) {}
    return () => { stop = true; clearInterval(iv); es?.close() }
  }, [applySnapshot])

  const onUpdateAlert = async (id, status) => {
    try { await api.updateAlertStatus(id, status) } catch (_) {}
    setDashboard((d) => d && ({
      ...d,
      alerts: d.alerts.map((a) => a.id === id ? { ...a, status } : a),
    }))
  }

  const onAddStocks = async (symbols) => {
    await api.addStocks(symbols)
    const snap = await api.dashboard()
    applySnapshot(snap, true)
  }
  const onRemoveStocks = async (symbols) => {
    await api.removeStocks(symbols)
    const snap = await api.dashboard()
    applySnapshot(snap, true)
  }
  const onScan = async () => {
    try { await api.scan(); } catch (_) {}
    const snap = await api.dashboard()
    applySnapshot(snap, true)
  }

  const data = dashboard || cached

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        connected={connected}
        view={view}
        setView={setView}
        onScan={onScan}
        theme={theme}
        onToggleTheme={toggleTheme}
        unread={data?.alerts?.filter((a) => a.status === 'fired' || a.status === 'seen').length || 0}
      />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-5">
        {error && (
          <div className="mb-3 card px-4 py-2.5 text-sm text-amber-400 border-amber-500/40">
            ⚠ {error}
          </div>
        )}
        {data && <MacroBanner macro={data.macro} connected={connected} />}

        {view === 'watchlist' && data && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <WatchlistView
                  stocks={data.watchlist}
                  deltas={deltas}
                  filters={filters}
                  onRemove={onRemoveStocks}
                  onUpdatePrefs={async (sym, prefs) => {
                    await api.updatePrefs(sym, prefs)
                  }}
                />
              </div>
              <div className="flex flex-col gap-4">
                <AlertPanel
                  alerts={data.alerts}
                  onUpdateAlert={onUpdateAlert}
                  onAddStocks={onAddStocks}
                  onScan={onScan}
                />
                <WatchlistManager
                  current={data.watchlist}
                  onAdd={onAddStocks}
                  onFilters={setFilters}
                />
              </div>
            </div>
          </>
        )}

        {view === 'heatmap' && <HeatmapView />}
        {view === 'backtest' && <BacktestView />}

        {!data && (
          <div className="flex justify-center py-24 text-slate-400">
            Loading market data…
          </div>
        )}
      </main>
    </div>
  )
}
