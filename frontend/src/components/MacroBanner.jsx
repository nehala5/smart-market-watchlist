import React from 'react'

const REGIME_COLOR = {
  calm: { text: 'text-emerald-400', dot: '#22c55e', label: 'Calm' },
  elevated: { text: 'text-amber-400', dot: '#f59e0b', label: 'Elevated' },
  stress: { text: 'text-red-400', dot: '#ef4444', label: 'Stress' },
}

export default function MacroBanner({ macro, connected }) {
  if (!macro) return null
  const regime = REGIME_COLOR[macro.regime] || REGIME_COLOR.calm
  return (
    <div className="card px-4 py-3 mb-4 flex items-center justify-between flex-wrap gap-3">
      <div className="flex items-center gap-3">
        <span className="text-lg">🌩</span>
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">Market Stress</div>
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-lg text-white">VIX ≈ {macro.vix}</span>
            <span className={`text-sm font-medium ${regime.text}`}>
              {regime.label}
            </span>
          </div>
        </div>
      </div>
      <div className="text-xs text-slate-500 max-w-xs text-right">
        {macro.note}. Alert thresholds auto-adjust in volatile regimes — a move that's
        normal in a stress market won't spam you.
      </div>
    </div>
  )
}
