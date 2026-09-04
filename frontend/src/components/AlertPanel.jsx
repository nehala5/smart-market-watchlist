import React from 'react'
import { ALERT_STATUS, ALERT_LABELS } from '../types.js'

const STATUS_COLOR = {
  fired: '#ef4444',
  seen: '#f59e0b',
  acknowledged: '#3b82f6',
  dismissed: '#64748b',
}
const STATUS_LABEL = {
  fired: 'New',
  seen: 'Seen',
  acknowledged: 'Acknowledged',
  dismissed: 'Dismissed',
}

export default function AlertPanel({ alerts, onUpdateAlert }) {
  // Sort: active first, then by time (decay is shown as age)
  const sorted = [...(alerts || [])].sort((a, b) => {
    const order = { dismissed: 3, acknowledged: 2, seen: 1, fired: 0 }
    const da = order[a.status] ?? 0
    const db = order[b.status] ?? 0
    if (da !== db) return da - db
    return new Date(b.created_at) - new Date(a.created_at)
  })
  const active = sorted.filter((a) => a.status === 'fired' || a.status === 'seen')
  const rest = sorted.filter((a) => a.status !== 'fired' && a.status !== 'seen')

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">
          Signal Feed
        </h3>
        {active.length > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">
            {active.length} active
          </span>
        )}
      </div>

      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {sorted.length === 0 && (
          <div className="text-xs text-slate-500 py-6 text-center">
            No signal alerts yet. Click ⟳ Scan to detect anomalies in your watchlist.
          </div>
        )}
        {sorted.map((a) => (
          <AlertRow key={a.id} alert={a} onUpdateAlert={onUpdateAlert} />
        ))}
      </div>
    </div>
  )
}

function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return Math.floor(s / 60) + 'm ago'
  if (s < 86400) return Math.floor(s / 3600) + 'h ago'
  return Math.floor(s / 86400) + 'd ago'
}

function AlertRow({ alert, onUpdateAlert }) {
  const [showWhy, setShowWhy] = React.useState(false)
  const signals = typeof alert.signals_json === 'string'
    ? safeParse(alert.signals_json)
    : alert.signals_json
  const color = STATUS_COLOR[alert.status] || '#64748b'
  const isActive = alert.status === 'fired' || alert.status === 'seen'

  return (
    <div
      className={`p-2.5 rounded-lg border text-sm ${
        isActive ? 'bg-panel2/60 border-border' : 'bg-panel/40 border-border/60 opacity-70'
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: color }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">{alert.symbol}</span>
            <span className="text-[10px] text-slate-500">{timeAgo(alert.created_at)}</span>
          </div>
          <div className="text-xs text-slate-300 mt-0.5">{alert.headline}</div>

          {showWhy && signals?.signals && (
            <div className="mt-2 text-[11px] text-slate-400 bg-bg rounded p-2 fade-in-up">
              {Object.entries(signals.signals)
                .filter(([k]) => k !== 'spread')
                .map(([k, z]) => (
                  <div key={k} className="flex justify-between py-0.5">
                    <span className="capitalize">{ALERT_LABELS[k] || k}</span>
                    <span className={`font-mono ${Math.abs(z) >= 1.8 ? 'text-red-400' : 'text-slate-400'}`}>
                      {z > 0 ? '+' : ''}{z.toFixed(2)}σ
                    </span>
                  </div>
                ))}
              {signals.volume_ratio ? (
                <div className="flex justify-between py-0.5">
                  <span>Volume</span>
                  <span className="font-mono text-slate-400">{signals.volume_ratio.toFixed(1)}x median</span>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        <button
          onClick={() => setShowWhy((s) => !s)}
          className="text-[11px] px-2 py-1 rounded bg-panel2 text-accent hover:bg-panel2/80"
        >
          {showWhy ? 'Hide' : 'Why?'}
        </button>
        {alert.status === 'fired' && (
          <button
            onClick={() => onUpdateAlert(alert.id, 'seen')}
            className="text-[11px] px-2 py-1 rounded bg-panel2 text-slate-300 hover:bg-border"
          >
            Mark seen
          </button>
        )}
        {(alert.status === 'fired' || alert.status === 'seen') && (
          <button
            onClick={() => onUpdateAlert(alert.id, 'acknowledged')}
            className="text-[11px] px-2 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30"
          >
            Acknowledge
          </button>
        )}
        {isActive && (
          <button
            onClick={() => onUpdateAlert(alert.id, 'dismissed')}
            className="text-[11px] px-2 py-1 rounded text-slate-500 hover:text-red-400 hover:bg-panel2"
          >
            Dismiss
          </button>
        )}
        {!isActive && (
          <span className="text-[10px] text-slate-500">{STATUS_LABEL[alert.status]}</span>
        )}
      </div>
    </div>
  )
}

function safeParse(s) {
  try { return JSON.parse(s) } catch { return null }
}
