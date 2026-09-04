export const LIGHT_STATUS = {
  normal: 'normal',
  watch: 'watch',
  unusual: 'unusual',
}

export const STATUS_META = {
  normal: { label: 'Normal', color: '#22c55e', rank: 0 },
  watch: { label: 'Watch', color: '#f59e0b', rank: 1 },
  unusual: { label: 'Unusual', color: '#ef4444', rank: 2 },
}

export const ALERT_STATUS = {
  fired: 'fired',
  seen: 'seen',
  acknowledged: 'acknowledged',
  dismissed: 'dismissed',
}

export const ALERT_LABELS = {
  return: 'big move',
  volatility: 'volatility spike',
  volume: 'volume surge',
  breakout: 'breakout',
  correlation: 'decoupled from peers',
  spread: 'spread widening',
}

export function trafficLight(composite) {
  if (composite >= 1.8) return LIGHT_STATUS.unusual
  if (composite >= 0.8) return LIGHT_STATUS.watch
  return LIGHT_STATUS.normal
}

export function freshnessLabel(sec) {
  if (sec < 90) return { label: 'Live', color: '#22c55e' }
  if (sec < 3600) return { label: '~' + Math.round(sec / 60) + 'm', color: '#f59e0b' }
  if (sec < 86400) return { label: '~' + Math.round(sec / 3600) + 'h', color: '#94a3b8' }
  return { label: 'stale', color: '#64748b' }
}
