import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

/* Two-part view:
 * 1) Anomaly intensity grid (which stocks are moving / rotated).
 * 2) Correlation matrix heatmap (which move together). */
export default function HeatmapView() {
  const [corr, setCorr] = useState(null)

  useEffect(() => {
    api.correlation().then(setCorr).catch(() => {})
  }, [])

  return (
    <div>
      <h2 className="text-lg font-bold text-white mb-1">Risk & Correlation Map</h2>
      <p className="text-xs text-slate-500 mb-4">
        Which stocks move together and which are isolated movers (alpha candidates).
      </p>

      {corr ? (
        <div className="card p-5 overflow-x-auto">
          <div className="text-xs text-slate-400 mb-3 uppercase tracking-wider">
            Correlation matrix — recent returns
          </div>
          <div className="inline-block">
            <table className="border-collapse">
              <thead>
                <tr>
                  <th className="p-0.5" />
                  {corr.symbols.map((s) => (
                    <th key={s} className="p-0.5 text-center text-[10px] font-mono text-slate-400">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {corr.symbols.map((a, i) => (
                  <tr key={a}>
                    <td className="p-0.5 text-right text-[10px] font-mono text-slate-400 pr-1">
                      {a}
                    </td>
                    {corr.symbols.map((b) => {
                      const v = corr.matrix[a]?.[b]
                      if (v == null) return <td key={b} className="w-7 h-7" />
                      return (
                        <td key={b} className="p-0.5">
                          <div
                            className="w-7 h-7 rounded flex items-center justify-center text-[9px] font-mono"
                            style={{ background: corrColor(v), color: Math.abs(v) > 0.5 ? '#0b0f17' : '#cbd5e1' }}
                            title={`${a} × ${b} = ${v}`}
                          >
                            {i !== corr.symbols.indexOf(b) ? (v > 0 ? '+' : '') + v.toFixed(1) : a}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex items-center gap-2 text-[10px] text-slate-500">
            <span>−1</span>
            <div className="h-2 flex-1 rounded-full"
              style={{ background: 'linear-gradient(to right, #3b82f6, #1e293b, #ef4444)' }} />
            <span>+1</span>
            <span className="ml-3 text-slate-400">Blue=move together · Red=opposite · dark=uncorrelated</span>
          </div>
        </div>
      ) : (
        <div className="text-slate-500 text-sm py-16 text-center">Loading correlation data…</div>
      )}
    </div>
  )
}

function corrColor(v) {
  if (v >= 0.7) return '#3b82f6'
  if (v >= 0.3) return '#1d4ed8'
  if (v <= -0.7) return '#ef4444'
  if (v <= -0.3) return '#b91c1c'
  return '#1e293b'
}
