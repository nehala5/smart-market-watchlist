/* Offline-first layer: caches the last dashboard snapshot in IndexedDB so the
 * app renders instantly and works without a network. Deltas are computed from
 * the cached snapshot vs the fresh one. */

const DB_NAME = 'signalwatch'
const DB_VERSION = 1
const STORE = 'snapshots'

let _dbPromise = null

function openDb() {
  if (_dbPromise) return _dbPromise
  _dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return reject(new Error('no indexedDB'))
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'key' })
        store.put({ key: 'last', savedAt: Date.now(), snapshot: null })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return _dbPromise
}

export async function saveSnapshot(snapshot) {
  try {
    const db = await openDb()
    return new Promise((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).put({
        key: 'last',
        savedAt: Date.now(),
        snapshot: { ...snapshot, cachedAt: Date.now() },
      })
      tx.oncomplete = () => resolve(true)
      tx.onerror = () => resolve(false)
    })
  } catch (e) {
    return false
  }
}

export async function loadSnapshot() {
  try {
    const db = await openDb()
    return new Promise((resolve) => {
      const tx = db.transaction(STORE, 'readonly')
      const req = tx.objectStore(STORE).get('last')
      req.onsuccess = () => resolve(req.result?.snapshot ?? null)
      req.onerror = () => resolve(null)
    })
  } catch (e) {
    return null
  }
}

/* Compute "what changed since last seen" between two snapshots of the same
 * watchlist, keyed by symbol. Returns a per-symbol delta object. */
export function computeDeltas(prev, next) {
  if (!prev?.watchlist || !next?.watchlist) return {}
  const bySym = {}
  for (const s of next.watchlist) bySym[s.symbol] = s
  const deltas = {}
  for (const p of prev.watchlist) {
    const n = bySym[p.symbol]
    if (!n) continue
    deltas[p.symbol] = {
      priceDelta: n.price ? ((n.price - (p.price || n.price)) / (p.price || n.price)) * 100 : 0,
      scoreDelta: n.composite - (p.composite || 0),
      lightChanged: (p.composite >= 1.8) !== (n.composite >= 1.8),
      crossedIntoWatch: (p.composite < 0.8 && n.composite >= 0.8),
      crossedIntoUnusual: (p.composite < 1.8 && n.composite >= 1.8),
    }
  }
  return deltas
}
