import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function BacktestView() {
  const [data, setData] = useState(null)
  const [days, setDays] = useState(5)

  useEffect(() => {
    setData(null)
    api.backtest(days).then(setData).catch(() => setData({ results: [] }))
  }, [days])

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-bold text-white">Backtest — What It Would Have Caught</h2>
        <div className="flex items-center gap-1">
          {[3, 5, 10].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-2.5 py-1 rounded-lg text-xs ${
                days === d ? 'bg-accent/20 text-accent' : 'text-slate-400 hover:bg-panel2'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        Replays the engine on past data to prove the signals react to history, not just today's snapshot.
      </p>

      {!data ? (
        <div className="text-slate-500 text-sm py-16 text-center">Running backtest…</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.results.map((r) => (
            <div key={r.symbol} className="card p-3.5">
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-white">{r.symbol}</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    r.flag_count > 0
                      ? 'bg-amber-500/20 text-amber-300'
                      : 'bg-panel2 text-slate-500'
                  }`}
                >
                  {r.flag_count} flagged
                </span>
              </div>
              {r.flag_count > 0 ? (
                <div className="mt-2 space-y-1">
                  {r.caught_in_last_days.slice(0, 4).map((c) => (
                    <div key={c.day} className="flex justify-between text-[11px] text-slate-400">
                      <span className="font-mono">{c.day}</span>
                      <span>
                        {c.day_ret_pct > 0 ? '+' : ''}{c.day_ret_pct}% · signal {c.composite}
                      </span>
                    </div>
                  ))}
                  {r.flag_count > 4 && (
                    <div className="text-[11px] text-slate-500">+{r.flag_count - 4} more</div>
                  )}
                </div>
              ) : (
                <div className="mt-2 text-[11px] text-slate-600">
                  No threshold-crossing signals in this window.
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
