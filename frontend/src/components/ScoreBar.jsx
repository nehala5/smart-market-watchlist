import React from 'react'

/* Signal-strength gauge: how far from normal is this stock's score?
 * 0-3 range: <0.8 green, 0.8-1.8 amber, >1.8 red. */
export default function ScoreBar({ value }) {
  const clamped = Math.min(3, Math.max(0, value || 0))
  const pct = (clamped / 3) * 100
  const color = value >= 1.8 ? '#ef4444' : value >= 0.8 ? '#f59e0b' : '#22c55e'
  return (
    <div className="flex flex-col items-center">
      <div className="w-full h-1.5 bg-panel2 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}
