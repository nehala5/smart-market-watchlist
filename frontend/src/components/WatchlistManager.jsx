import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function WatchlistManager({ current, onAdd, onFilters }) {
  const [universe, setUniverse] = useState([])
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState({})
  const currentSyms = new Set((current || []).map((s) => s.symbol))

  useEffect(() => {
    api.universe().then(setUniverse).catch(() => {})
  }, [])

  const sectorSet = []
  for (const s of universe) if (!sectorSet.includes(s.sector)) sectorSet.push(s.sector)

  const filtered = universe.filter((s) =>
    (s.symbol + ' ' + s.name).toLowerCase().includes(q.toLowerCase())
  )

  const toggleFilter = (key, val) =>
    setFilters((f) => {
      const next = { ...f }
      if (next[key] === val) delete next[key]
      else next[key] = val
      return next
    })

  useEffect(() => { onFilters(filters) }, [filters, onFilters])

  const add = async (sym) => { await onAdd([sym]) }

  return (
    <div className="card p-4">
      <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3">Manage</h3>

      {/* Filters */}
      <div className="mb-3">
        <div className="text-[11px] text-slate-500 mb-1.5">Filter watchlist</div>
        <div className="flex flex-wrap gap-1.5">
          {['normal', 'watch', 'unusual'].map((l) => (
            <Chip
              key={l}
              active={filters.light === l}
              onClick={() => toggleFilter('light', l)}
            >
              {l === 'normal' ? '🟢' : l === 'watch' ? '🟡' : '🔴'} {l}
            </Chip>
          ))}
          <Chip
            active={!!filters.changedRecent}
            onClick={() => toggleFilter('changedRecent', 2)}
          >
            ⏱ moved in 2h
          </Chip>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {sectorSet.map((sec) => (
            <Chip
              key={sec}
              active={filters.sector === sec}
              onClick={() => toggleFilter('sector', sec)}
            >
              {sec}
            </Chip>
          ))}
        </div>
        {Object.keys(filters).length > 0 && (
          <button
            onClick={() => setFilters({})}
            className="text-[11px] text-accent mt-2 hover:underline"
          >
            ✕ Clear filters
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search symbol or name…"
          className="w-full bg-panel2 border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent"
        />
      </div>

      <div className="mt-2 max-h-56 overflow-y-auto pr-1">
        {filtered.length === 0 && (
          <div className="text-xs text-slate-500 py-4 text-center">No matches</div>
        )}
        {filtered.slice(0, 30).map((s) => {
          const inList = currentSyms.has(s.symbol)
          return (
            <div
              key={s.symbol}
              className="flex items-center justify-between py-1.5 text-sm group"
            >
              <div>
                <span className="font-mono font-semibold text-white">{s.symbol}</span>
                <span className="text-xs text-slate-500 ml-2">{s.name}</span>
              </div>
              {inList ? (
                <span className="text-[10px] text-slate-600">added</span>
              ) : (
                <button
                  onClick={() => add(s.symbol)}
                  className="text-xs px-2 py-1 rounded bg-panel2 text-accent hover:bg-border"
                >
                  + Add
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Chip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-2 py-1 rounded-full border transition-colors ${
        active
          ? 'bg-accent/20 border-accent text-accent'
          : 'bg-panel2 border-border text-slate-400 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}
