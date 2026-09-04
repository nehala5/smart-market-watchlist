import React from 'react'
import { trafficLight, STATUS_META, freshnessLabel } from '../types.js'
import Sparkline from './Sparkline.jsx'
import ScoreBar from './ScoreBar.jsx'

export default function WatchlistView({ stocks, deltas, filters, onRemove, onUpdatePrefs }) {
  const filtered = useSmartFilter(stocks, filters)

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold text-white">Watchlist</h2>
        <span className="text-xs text-slate-500">
          Sorted by anomaly risk · {filtered.length} holdings
        </span>
      </div>
      <div className="space-y-2.5">
        {filtered.map((s) => (
          <StockRow
            key={s.symbol}
            stock={s}
            delta={deltas?.[s.symbol]}
            onRemove={onRemove}
            onUpdatePrefs={onUpdatePrefs}
          />
        ))}
        {filtered.length === 0 && (
          <div className="card p-6 text-center text-slate-500 text-sm">
            No stocks match your filters.
          </div>
        )}
      </div>
    </div>
  )
}

function useSmartFilter(stocks, filters) {
  return React.useMemo(() => {
    let list = [...(stocks || [])]
    if (filters.light) {
      list = list.filter((s) => trafficLight(s.composite) === filters.light)
    }
    if (filters.sector) {
      list = list.filter((s) => s.sector === filters.sector)
    }
    if (filters.changedRecent) {
      const cutoff = filters.changedRecent * 3600
      list = list.filter((s) => (s.freshness_sec ?? Infinity) <= cutoff + 30)
    }
    // Default: rank by composite risk
    list.sort((a, b) => (b.composite || 0) - (a.composite || 0))
    return list
  }, [stocks, filters])
}

function StockRow({ stock, delta, onRemove, onUpdatePrefs }) {
  const [expanded, setExpanded] = React.useState(false)
  const [menuOpen, setMenuOpen] = React.useState(false)
  const light = trafficLight(stock.composite)
  const fs = freshnessLabel(stock.freshness_sec)
  const up = (stock.change_pct || 0) >= 0

  return (
    <div className={`card p-3.5 fade-in-up border-l-4 ${light === 'unusual' ? 'border-l-red-500' : light === 'watch' ? 'border-l-amber-500' : 'border-l-emerald-600'}`}>
      <div className="flex items-center gap-3" onClick={() => setExpanded((e) => !e)}>
        {/* Direction dot: green=up, red=down (instant read) */}
        <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: up ? '#22c55e' : '#ef4444' }} />

        {/* Name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">{stock.symbol}</span>
            <span className="text-xs text-slate-500">{stock.sector_short}</span>
            {/* Anomaly badge (left border + this label carry the anomaly signal) */}
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${light === 'unusual' ? 'bg-red-500/20 text-red-400' : light === 'watch' ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-400'}`}>
              {light === 'unusual' ? 'Unusual' : light === 'watch' ? 'Watch' : 'Normal'}
            </span>
            {stock.catalyst_today && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300" title={
                (stock.events || []).map((e) => `${e.title} · ${e.date}`).join('\n')
              }>
                📅 Catalyst
              </span>
            )}
            {stock.insider && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300" title={stock.insider.detail}>
                🔍 Insider
              </span>
            )}
            {delta?.lightChanged && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">↕ changed</span>
            )}
          </div>
          <div className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
            <span style={{ color: up ? '#22c55e' : '#ef4444' }}>
              {up ? '▲' : '▼'} {Math.abs(stock.change_pct || 0).toFixed(2)}% today
            </span>
            <span className="text-slate-600">·</span>
            <span>rel {stock.relative_change >= 0 ? '+' : ''}{stock.relative_change}% vs sector</span>
          </div>
        </div>

        {/* Price */}
        <div className="text-right">
          <div className="font-mono font-bold text-white">{stock.price?.toFixed(2)}</div>
          <div className="text-[10px] text-slate-500">
            vol {stock.volume_ratio?.toFixed(1)}x
          </div>
        </div>

        {/* Sparkline */}
        <div className="hidden md:block">
          <Sparkline data={stock.series_prices} width={110} height={36} />
        </div>

        {/* Score bar */}
        <div className="w-24">
          <ScoreBar value={stock.composite} />
          <div className="text-center text-[10px] text-slate-500 mt-1">
            {stock.composite.toFixed(2)}
          </div>
        </div>

        {/* freshness */}
        <div className="hidden lg:flex items-center gap-1 text-[10px]" style={{ color: fs.color }}>
          <span>{fs.label}</span>
        </div>
      </div>

      {/* Expandable drill-down */}
      {expanded && <StockDetail stock={stock} />}

      {/* Row actions */}
      <div className="flex items-center gap-2 mt-2 justify-end">
        <span className="text-[10px] text-slate-600">{(stock.price ?? 0).toFixed(0)} pts</span>
        <div className="relative">
          <button
            onClick={(e) => { e.stopPropagation(); setMenuOpen((m) => !m) }}
            className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-panel2"
          >
            ···
          </button>
          {menuOpen && (
            <div className="absolute right-0 bottom-full mb-1 z-20 card shadow-xl p-1 w-44">
              <button
                className="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-panel2 rounded"
                onClick={(e) => { e.stopPropagation(); setExpanded(true); setMenuOpen(false) }}
              >
                View detail
              </button>
              <button
                className="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-panel2 rounded"
                onClick={async (e) => {
                  e.stopPropagation(); setMenuOpen(false)
                  await onUpdatePrefs(stock.symbol, { interest_level: 'low' })
                }}
              >
                🔕 Low interest
              </button>
              <button
                className="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-panel2 rounded"
                onClick={async (e) => {
                  e.stopPropagation(); setMenuOpen(false)
                  await onUpdatePrefs(stock.symbol, { interest_level: 'high' })
                }}
              >
                🔥 High risk watch
              </button>
              <button
                className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-panel2 rounded"
                onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onRemove([stock.symbol]) }}
              >
                Remove
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StockDetail({ stock }) {
  const sig = stock.signals || {}
  const fmt = (v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}σ`
  const rows = [
    { key: 'return', label: 'Price move' },
    { key: 'volatility', label: 'Volatility' },
    { key: 'volume', label: 'Volume' },
    { key: 'breakout', label: 'Trend / Breakout' },
    { key: 'correlation', label: 'Peers' },
  ]
  return (
    <div className="mt-3 pt-3 border-t border-border fade-in-up">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          {rows.map((r) => (
            <div key={r.key} className="flex items-center justify-between text-sm">
              <span className="text-slate-400">{r.label}</span>
              <span className={`font-mono ${Math.abs(sig[r.key] || 0) >= 1.8 ? 'text-red-400' : Math.abs(sig[r.key] || 0) >= 0.8 ? 'text-amber-400' : 'text-slate-400'}`}>
                {fmt(sig[r.key] || 0)}
              </span>
            </div>
          ))}
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">24h score trend</span>
            <span className="text-slate-400">…</span>
          </div>
        </div>
        <div className="space-y-2">
          <div className="text-sm text-slate-400">
            Latest composite <span className="font-mono text-white">{stock.composite.toFixed(2)}</span>
          </div>
          <div className="text-sm text-slate-400">
            Volume ratio <span className="font-mono text-white">{stock.volume_ratio?.toFixed(2)}x</span>
          </div>
          <div className="text-sm text-slate-400">
            vs sector <span className={`font-mono ${stock.relative_change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {stock.relative_change >= 0 ? '+' : ''}{stock.relative_change}%
            </span>
          </div>
          {stock.rs_20d != null && (
            <div className="text-sm text-slate-400">
              20-day RS{' '}
              <span className={`font-mono ${stock.rs_20d >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {stock.rs_20d >= 0 ? '+' : ''}{stock.rs_20d}%
              </span>
            </div>
          )}
          {stock.pos_in_52w != null && (
            <div className="text-sm text-slate-400">
              52w range position{' '}
              <span className="font-mono text-white">{stock.pos_in_52w}%</span>
            </div>
          )}
          {stock.insider && (
            <div className="text-[11px] text-sky-300">
              🔍 {stock.insider.detail}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
