import React from 'react'

const VIEWS = [
  { key: 'watchlist', label: 'Watchlist' },
  { key: 'heatmap', label: 'Risk Map' },
  { key: 'backtest', label: 'Backtest' },
]

export default function Header({ connected, view, setView, onScan, unread }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/90 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-bold text-white">
            <span className="text-xl">📡</span>
            <span className="tracking-tight">Signal<span className="text-accent">Watch</span></span>
          </div>
          <span className="hidden sm:inline text-xs text-slate-500">
            Smart market watchlist
          </span>
        </div>

        <nav className="flex items-center gap-1">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                view === v.key ? 'bg-accent/20 text-accent' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {v.label}
            </button>
          ))}
          <button
            onClick={onScan}
            className="ml-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors"
            title="Re-scan for anomalies"
          >
            ⟳ Scan
          </button>
          <div className="ml-3 flex items-center gap-1.5 text-xs text-slate-500">
            <span
              className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-slate-600'}`}
            />
            {connected ? 'Live' : 'Cached'}
          </div>
          {unread > 0 && (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs font-bold">
              {unread}
            </span>
          )}
        </nav>
      </div>
    </header>
  )
}
