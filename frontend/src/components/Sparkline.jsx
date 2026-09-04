import React from 'react'

export default function Sparkline({ data, width = 110, height = 36, color }) {
  if (!data || data.length < 2) {
    return <svg width={width} height={height} />
  }
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - 4) + 2
    const y = height - 3 - ((v - min) / range) * (height - 6)
    return [x, y]
  })
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const up = data[data.length - 1] >= data[0]
  const c = color || (up ? '#22c55e' : '#ef4444')
  const area =
    `M${pts[0][0]},${height} ` + pts.map((p) => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ') +
    ` L${pts[pts.length - 1][0]},${height} Z`
  return (
    <svg width={width} height={height} className="overflow-visible">
      <path d={area} fill={c} opacity={0.12} />
      <path d={line} fill="none" stroke={c} strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  )
}
