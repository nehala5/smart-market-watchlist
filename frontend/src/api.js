const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json()
}

export const api = {
  universe: () => request('/universe'),
  dashboard: () => request('/dashboard'),
  watchlist: () => request('/watchlist'),
  addStocks: (symbols) => request('/watchlist/add', {
    method: 'POST', body: JSON.stringify({ symbols }),
  }),
  removeStocks: (symbols) => request('/watchlist/remove', {
    method: 'POST', body: JSON.stringify({ symbols }),
  }),
  updatePrefs: (symbol, prefs) => request(`/prefs/${symbol}`, {
    method: 'PUT', body: JSON.stringify(prefs),
  }),
  updateAlertStatus: (id, status) => request(`/alerts/${id}/status`, {
    method: 'POST', body: JSON.stringify({ status }),
  }),
  scan: () => request('/scan', { method: 'POST' }),
  stock: (symbol) => request(`/stock/${symbol}`),
  correlation: () => request('/correlation'),
  backtest: (days = 5) => request(`/backtest?days=${days}`),
}
