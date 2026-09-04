import React from 'react'

/* "Why" popover explaining an anomaly in concrete, human terms.
 * Renders a small annotated breakdown of z-score signals. */
export default function ExplainTooltip({ signals, children }) {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef(null)

  React.useEffect(() => {
    if (!open) return
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  if (!signals) return <>{children}</>

  const rows = Object.entries(signals).filter(([k]) => k !== 'spread')
  return (
    <span className="relative inline-block" ref={ref}>
      <span onClick={() => setOpen((o) => !o)} className="cursor-pointer">
        {children}
      </span>
      {open && (
        <div className="absolute z-50 mt-1 bg-panel2 border border-border rounded-lg shadow-2xl p-3 w-60 text-left">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
            Signal breakdown
          </div>
          <div className="space-y-1">
            {rows.map(([k, z]) => {
              const mag = Math.abs(z)
              const color = mag >= 1.8 ? 'text-red-400' : mag >= 0.8 ? 'text-amber-400' : 'text-slate-400'
              return (
                <div key={k} className="flex items-center justify-between text-[11px]">
                  <span className="capitalize text-slate-300">{k}</span>
                  <span className={`font-mono ${color}`}>
                    {z > 0 ? '+' : ''}{z.toFixed(2)}σ
                  </span>
                </div>
              )
            })}
          </div>
          <div className="mt-2 pt-2 border-t border-border text-[10px] text-slate-500">
            σ = how many standard deviations from this stock's own recent norm.
          </div>
        </div>
      )}
    </span>
  )
}
