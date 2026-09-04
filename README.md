# 📡 SignalWatch — Smart Market Watchlist

A **smart market watchlist** that doesn't just track prices — it tells you what has
*meaningfully changed* since you last looked, and what deserves your attention now.

Built for the **Groww CODE 2026** challenge. Full-stack (React + FastAPI), offline-first,
with a multi-signal anomaly engine at its core.

---

## 🏆 What makes this different from an obvious watchlist

The core idea is a **composite anomaly score** per stock instead of raw price moves.

| Signal | What it measures | Why it matters |
|--------|------------------|----------------|
| **Price move** | Latest move vs. the stock's own history (z-score) | "Did something *actually* happen today?" |
| **Volatility** | Realized vol vs. its 20-bar rolling norm | Regime spikes, not steady trends |
| **Volume** | Volume vs. 20-day median | Liquidity surge = informed interest |
| **Breakout** | Distance from 20/50-bar high–low range | Momentum / trend resolution |
| **Correlation** | Decoupling from sector peers | **Isolated movers (alpha candidates)** |

Each signal is a **z-score relative to that stock's own history**, so a 1% move in
Apple ≠ a 1% move in a clean-energy small-cap. Signals are weighted into **one
composite score** with **sector-normalized thresholds** (tech is 2× more volatile
than utilities, so it needs to move more to be "unusual").

**Traffic lights** from the composite, so you read the screen in half a second:
- 🟢 **Normal** (score < 0.8)
- 🟡 **Watch** (0.8 – 1.8)
- 🔴 **Unusual** (≥ 1.8)

Then the design goes further:

- **Explainability** — every alert has a "Why?" breakdown showing each z-score.
  Not "vol high" but *"volatility spike, −0.29% vs sector, 3.7x volume"*.
- **Alert lifecycle** — `fired → seen → acknowledged → dismissed`. You only ever
  act on each signal once; it stops re-surfacing.
- **Peer context** — every row shows its move **relative to its sector**, not absolute.
- **Time-decay** — old signals fade (12h half-life) so yesterday's move doesn't
  clutter today's view.
- **Macro-aware thresholds** — a VIX-style stress proxy (from cross-sectional
  dispersion) is shown, and the thresholds conceptually auto-adjust in stress regimes.
- **Offline-first** — the last snapshot is cached in IndexedDB; the app renders
  instantly and works without a network, computing "what changed" deltas on reconnect.
- **Backtest mode** — replays the scoring on past data to *prove* the signals react
  to history rather than being tuned to today.
- **Correlation heatmap** — see which holdings move together vs. which are isolated.

---

## 🧱 Architecture

```
groww
├── backend/                 # FastAPI + SQLite
│   ├── main.py              # Routes, SSE, live-market simulator, backtest, correlation
│   ├── engine.py            # The anomaly scoring engine (heart of the product)
│   ├── database.py          # SQLite schema + helpers
│   ├── seed.py              # Seeds 45 stocks × 260 days of realistic history
│   └── requirements.txt
└── frontend/                # React + Vite + Tailwind
    └── src/
        ├── App.jsx          # Dashboard shell, polling + SSE
        ├── api.js           # API client
        ├── offline.js       # IndexedDB cache + delta computation
        ├── types.js         # Traffic-light / alert constants
        └── components/      # Header, MacroBanner, WatchlistView, AlertPanel,
                             # WatchlistManager, HeatmapView, BacktestView,
                             # Sparkline, ScoreBar, ExplainTooltip
```

### Data flow
```
Backend seeds 45 stocks × 260 days
        │
        ▼
Anomaly engine computes composite score per stock (5 signals, z-scores)
        │
        ▼
FastAPI serves /api/dashboard · /api/stream (SSE) · /api/backtest · /api/correlation
        │
        ▼
React polls every 8s + opens SSE → live in-place updates, no page refresh
        │
        ▼
Snapshot cached to IndexedDB → instant render + "what changed" deltas offline
```

### Reliability & edge cases handled
- **Duplicate/stale data** — quotes keyed by `(symbol, ts)`; reseeding is idempotent
  (clears old market data). Fixed a real bug where reseeding duplicated timelines.
- **Missing/invalid history** — a stock with < 30 samples is skipped instead of
  throwing; scoring degrades gracefully.
- **Bad ticks** — prices are bounded (`max(0.2, …)`), so wild single-sample jumps
  can't corrupt the engine.
- **Sparse watchlists** — empty watchlists fall back to a seeded demo list.
- **DB failure** — the engine's async DB access is isolated; a scoring error returns
  `None` rather than crashing the request.

---

## ▶️ Running it

### Backend (Python 3.10+)
```bash
cd backend
pip install -r requirements.txt

# First run (or run automatically via the app lifespan):
python -c "import database; import asyncio; asyncio.run(database.init_db())"
python -c "import seed; import asyncio; asyncio.run(seed.seed())"

uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev
# opens at http://127.0.0.1:5173  (proxies /api → :8000)
```

---

## 📡 API surface

| Endpoint | Description |
|----------|-------------|
| `GET /api/universe` | All tradable symbols + sectors |
| `GET /api/watchlist` | Current watchlist with prefs |
| `POST /api/watchlist/add` | Add symbols |
| `POST /api/watchlist/remove` | Remove symbols |
| `GET /api/dashboard` | Scored watchlist + alerts + macro |
| `GET /api/stock/{sym}` | Single-stock signal breakdown |
| `GET /api/stream` | **SSE** — live snapshot pushes |
| `POST /api/alerts/{id}/status` | Alert lifecycle transition |
| `POST /api/scan` | Re-scan for anomalies |
| `GET /api/backtest?days=N` | Historical replay of signals |
| `GET /api/correlation` | Cross-holding correlation matrix |
| `PUT /api/prefs/{sym}` | Per-stock interest/threshold prefs |

---

## 🎯 The pitch

Most watchlists show you a *price*. This one shows you **what changed, why it
matters, and whether it's noise** — ranked by an explainable anomaly score with
peer context, time decay, and a full alert lifecycle. It's the difference between
watching the tape and *understanding it*.
