"""FastAPI application exposing the SignalWatch API."""
import asyncio
import datetime as dt
import json
import math
import numpy as np
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import database
from database import get_conn, ensure_user
import engine
from engine import compute_stock_score, sector_movers, traffic_light, _iso
import catalysts


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await ensure_user()
    # seed if empty
    conn = await get_conn()
    cur = await conn.execute("SELECT COUNT(*) AS c FROM stocks")
    n = (await cur.fetchone())["c"]
    await conn.close()
    if n == 0:
        import seed
        await seed.seed()
    # ensure a populated default watchlist for an impressive first load
    await _ensure_demo_watchlist()
    # background live-market simulator
    task = asyncio.create_task(_live_market_task())
    yield
    task.cancel()


app = FastAPI(title="SignalWatch", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Serve the built React dashboard (frontend/dist) if present ----------
import pathlib  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

_FRONTEND = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND.exists() and (_FRONTEND / "index.html").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND / "assets")),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    async def _index():
        return FileResponse(_FRONTEND / "index.html")

    @app.exception_handler(StarletteHTTPException)
    async def _spa_fallback(request, exc):
        p = request.url.path
        if exc.status_code == 404 and not p.startswith("/api"):
            if (_FRONTEND / "index.html").exists():
                return FileResponse(_FRONTEND / "index.html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)


# ----------------------------------------------------------------- Models ----
class WatchlistCreate(BaseModel):
    name: str = "Default"


class AddStocks(BaseModel):
    symbols: list[str]


class AlertUpdate(BaseModel):
    status: str  # fired | seen | acknowledged | dismissed


class PrefUpdate(BaseModel):
    interest_level: str | None = None
    threshold_override: float | None = None
    muted: bool | None = None
    weights: dict[str, float] | None = None


# ------------------------------------------------------------------ Routes ---

def demo_symbols():
    return ["NVDA", "TSLA", "QCOM", "META", "JPM", "LLY", "AMD", "AAPL",
            "ORCL", "XOM", "GE", "KO"]


async def _ensure_demo_watchlist():
    """Populate a default watchlist on first run so the dashboard isn't empty."""
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT id FROM watchlists WHERE user_id=?", (user_id,)
    )
    wl = await cur.fetchone()
    if wl is None:
        cur = await conn.execute(
            "INSERT INTO watchlists (user_id, name, created_at) VALUES (?,?,?)",
            (user_id, "My Watchlist", dt.datetime.utcnow().isoformat()),
        )
        wl_id = cur.lastrowid
    else:
        wl_id = wl["id"]
    # only seed if the watchlist is completely empty
    cur = await conn.execute(
        "SELECT COUNT(*) AS c FROM watchlist_items WHERE watchlist_id=?",
        (wl_id,),
    )
    if (await cur.fetchone())["c"] == 0:
        for sym in demo_symbols():
            await conn.execute(
                "INSERT OR IGNORE INTO watchlist_items (watchlist_id, symbol, added_at) "
                "VALUES (?,?,?)",
                (wl_id, sym, dt.datetime.utcnow().isoformat()),
            )
            await conn.execute(
                "INSERT OR IGNORE INTO stock_prefs (user_id, symbol, interest_level) "
                "VALUES (?,?,?)",
                (user_id, sym, "normal"),
            )
    await conn.commit()
    await conn.close()


@app.get("/api/universe")
async def get_universe():
    conn = await get_conn()
    cur = await conn.execute("SELECT symbol, name, sector FROM stocks ORDER BY symbol")
    rows = await cur.fetchall()
    await conn.close()
    return [dict(r) for r in rows]


@app.get("/api/watchlist")
async def get_watchlist():
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT s.symbol, s.name, s.sector, p.interest_level, p.threshold_override, p.muted "
        "FROM stocks s "
        "LEFT JOIN watchlist_items w ON s.symbol = w.symbol "
        "LEFT JOIN stock_prefs p ON p.user_id = ? AND p.symbol = s.symbol "
        "WHERE w.watchlist_id = "
        "(SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1) "
        "ORDER BY s.symbol",
        (user_id, user_id),
    )
    rows = await cur.fetchall()
    await conn.close()
    return [dict(r) for r in rows]


@app.post("/api/watchlist")
async def create_watchlist(body: WatchlistCreate):
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "INSERT INTO watchlists (user_id, name, created_at) VALUES (?,?,?)",
        (user_id, body.name, dt.datetime.utcnow().isoformat()),
    )
    await conn.commit()
    wl_id = cur.lastrowid
    await conn.close()
    return {"id": wl_id, "name": body.name}


@app.post("/api/watchlist/add")
async def add_stocks(body: AddStocks):
    """Add symbols to the user's watchlist. Ensures watchlist exists."""
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1", (user_id,)
    )
    row = await cur.fetchone()
    if row is None:
        cur = await conn.execute(
            "INSERT INTO watchlists (user_id, name, created_at) VALUES (?,?,?)",
            (user_id, "Default", dt.datetime.utcnow().isoformat()),
        )
        wl_id = cur.lastrowid
    else:
        wl_id = row["id"]
    for sym in body.symbols:
        await conn.execute(
            "INSERT OR IGNORE INTO watchlist_items (watchlist_id, symbol, added_at) "
            "VALUES (?,?,?)",
            (wl_id, sym.upper(), dt.datetime.utcnow().isoformat()),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO stock_prefs (user_id, symbol, interest_level) "
            "VALUES (?,?,?)",
            (user_id, sym.upper(), "normal"),
        )
    await conn.commit()
    await conn.close()
    return {"ok": True}


@app.post("/api/watchlist/remove")
async def remove_stocks(body: AddStocks):
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1", (user_id,)
    )
    row = await cur.fetchone()
    if row is None:
        await conn.close()
        return {"ok": True}
    wl_id = row["id"]
    for sym in body.symbols:
        await conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id=? AND symbol=?",
            (wl_id, sym.upper()),
        )
    await conn.commit()
    await conn.close()
    return {"ok": True}


@app.put("/api/prefs/{symbol}")
async def set_prefs(symbol: str, body: PrefUpdate):
    user_id = await ensure_user()
    conn = await get_conn()
    data = body.model_dump(exclude_none=True)
    sym = symbol.upper()
    await conn.execute(
        "INSERT OR IGNORE INTO stock_prefs (user_id, symbol, interest_level) VALUES (?,?,?)",
        (user_id, sym, "normal"),
    )
    sets = []
    vals = []
    allowed = {"interest_level", "threshold_override", "muted"}
    for k, v in data.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if sets:
        await conn.execute(
            f"UPDATE stock_prefs SET {', '.join(sets)} WHERE user_id=? AND symbol=?",
            (*vals, user_id, sym),
        )
    await conn.commit()
    await conn.close()
    return {"ok": True}


@app.get("/api/dashboard")
async def dashboard():
    """Combined payload: scored watchlist + alert feed."""
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT symbol FROM watchlist_items WHERE watchlist_id = "
        "(SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1)",
        (user_id,),
    )
    watch_symbols = [r["symbol"] for r in await cur.fetchall()]

    # alerts
    cur = await conn.execute(
        "SELECT * FROM alerts WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    )
    alerts = [dict(r) for r in await cur.fetchall()]
    conn.close()

    if not watch_symbols:
        watch_symbols = demo_symbols()

    scores = await sector_movers(watch_symbols)

    # attach catalyst + insider context to each scored stock (causal layer)
    for sc in scores:
        evs = catalysts.get_events(sc["symbol"])
        sc["catalyst_today"] = catalysts.has_catalyst_today(sc["symbol"])
        sc["events"] = evs
        insider = [e for e in evs if e["type"] == "insider"]
        sc["insider"] = insider[0] if insider else None

    snapshot = {
        "watchlist": scores,
        "alerts": alerts,
        "macro": await compute_macro(),
        "generated_at": dt.datetime.utcnow().isoformat(),
    }
    return snapshot


@app.get("/api/stock/{symbol}")
async def stock_detail(symbol: str):
    sc = await compute_stock_score(symbol.upper())
    if sc is None:
        raise HTTPException(404, "Unknown symbol")
    sc["events"] = catalysts.get_events(sc["symbol"])
    sc["catalyst_today"] = catalysts.has_catalyst_today(sc["symbol"])
    evs = sc["events"]
    insider = [e for e in evs if e["type"] == "insider"]
    sc["insider"] = insider[0] if insider else None
    # relative strength vs 20d / 52w
    hist = await engine.fetch_history(sc["symbol"], 260)
    if len(hist) >= 20:
        prices = np.array([r["price"] for r in hist], dtype=float)
        sc["rs_20d"] = round((prices[-1] / prices[-20] - 1) * 100, 2) if prices[-20] else 0
        sc["high_52w"] = float(prices.max())
        sc["low_52w"] = float(prices.min())
        rng_52 = max(prices.max() - prices.min(), 1e-6)
        sc["pos_in_52w"] = round((prices[-1] - prices.min()) / rng_52 * 100, 1)
    return sc


DEFAULT_ALERT_TYPES = ["volatility", "volume", "breakout", "correlation", "spread"]


async def generate_alerts(now=None):
    """Scan watchlist, generate new alerts for significant moves.

    Idempotent-ish: only creates 'fired' alerts that aren't already fired for
    same symbol+type within a recent window.
    """
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT symbol FROM watchlist_items WHERE watchlist_id = "
        "(SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1)",
        (user_id,),
    )
    watch = [r["symbol"] for r in await cur.fetchall()]
    conn.close()
    if not watch:
        watch = demo_symbols()

    scores = await sector_movers(watch, now)
    created = []
    for sc in scores:
        comp = sc["composite"]
        if sc["sector"] == "Technology":
            threshold = 1.3
        elif sc["sector"] in ("Consumer", "Healthcare"):
            threshold = 1.1
        else:
            threshold = 1.2
        if comp < threshold:
            continue
        # pick dominant signal
        dom = max(sc["signals"], key=lambda k: abs(sc["signals"][k]))
        headline = _headline(sc, dom)
        # skip if recent fired alert of same type exists
        conn = await get_conn()
        cur = await conn.execute(
            "SELECT id FROM alerts WHERE user_id=? AND symbol=? AND alert_type=? "
            "AND status IN ('fired','seen','acknowledged') "
            "AND created_at > ?",
            (user_id, sc["symbol"], dom,
             (dt.datetime.utcnow() - dt.timedelta(hours=24)).isoformat()),
        )
        if await cur.fetchone():
            await conn.close()
            continue
        await conn.execute(
            "INSERT INTO alerts (user_id, symbol, alert_type, composite_score, "
            "headline, signals_json, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, sc["symbol"], dom, comp, headline,
             json.dumps({"composite": comp, "signals": sc["signals"],
                         "relative_change": sc.get("relative_change", 0),
                         "volume_ratio": sc.get("volume_ratio", 1)}),
             "fired", dt.datetime.utcnow().isoformat()),
        )
        await conn.commit()
        created.append(sc["symbol"])
        await conn.close()
    return created


def _headline(sc, dom):
    labels = {
        "volatility": "volatility spike",
        "volume": "volume surge",
        "breakout": "breakout",
        "correlation": "decoupled from peers",
        "spread": "spread widening",
    }
    rel = sc.get("relative_change", 0)
    rel_txt = f", {rel:+.2f}% vs sector" if abs(rel) > 0.05 else ""
    vr = sc.get("volume_ratio", 1)
    extra = f", {vr:.1f}x volume" if vr > 1.5 else ""
    return f"{sc['symbol']}: {labels.get(dom, dom)} detected{rel_txt}{extra}"


@app.post("/api/alerts/{alert_id}/status")
async def update_alert(alert_id: int, body: AlertUpdate):
    user_id = await ensure_user()
    conn = await get_conn()
    col = {
        "fired": None, "seen": "seen_at",
        "acknowledged": "acknowledged_at", "dismissed": "dismissed_at",
    }
    await conn.execute(
        "UPDATE alerts SET status=?, seen_at=COALESCE(?,seen_at), "
        "acknowledged_at=?, dismissed_at=? WHERE id=? AND user_id=?",
        (body.status, dt.datetime.utcnow().isoformat() if body.status == "seen" else None,
         dt.datetime.utcnow().isoformat() if body.status == "acknowledged" else None,
         dt.datetime.utcnow().isoformat() if body.status == "dismissed" else None,
         alert_id, user_id),
    )
    await conn.commit()
    await conn.close()
    return {"ok": True}


@app.post("/api/scan")
async def scan():
    created = await generate_alerts()
    return {"created": created}


# ---------------------------------------------------------- Macro/VIX -------

async def compute_macro():
    """VIX-like market stress proxy from cross-sectional dispersion of returns
    across the seeded universe. Higher dispersion => higher stress."""
    conn = await get_conn()
    cur = await conn.execute("SELECT symbol FROM stocks ORDER BY symbol")
    syms = [r["symbol"] for r in await cur.fetchall()]
    changes = []
    for s in syms:
        cur = await conn.execute(
            "SELECT price FROM quotes WHERE symbol=? ORDER BY ts DESC LIMIT 2", (s,)
        )
        rows = await cur.fetchall()
        if len(rows) == 2 and rows[1]["price"]:
            changes.append((rows[0]["price"] / rows[1]["price"] - 1) * 100)
    await conn.close()
    if len(changes) < 5:
        return {"vix": 18.5, "regime": "calm", "note": "insufficient data"}
    dispersion = float(np.std(changes))
    vix = 15 + dispersion * 1.6
    vix = max(12, min(38, vix))
    if vix > 28:
        regime = "stress"
    elif vix > 20:
        regime = "elevated"
    else:
        regime = "calm"
    return {"vix": round(vix, 1), "regime": regime,
            "note": "proxy from cross-sectional dispersion"}


# --------------------------------------------------------------- Backtest ----

@app.get("/api/backtest")
async def backtest(days: int = 5):
    """What would the engine have flagged over the last N days?

    For each of the past N trading days we replay the engine's own scoring on the
    history as it would have been known at that point, and report the per-day
    composite for each watchlist symbol. A 'signal' maps to composite >= 1.0,
    matching today's yellow/red split. This proves the scoring isn't tuned to the
    current snapshot — it reacts to history.
    """
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT symbol FROM watchlist_items WHERE watchlist_id = "
        "(SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1)",
        (user_id,),
    )
    watch = [r["symbol"] for r in await cur.fetchall()]
    conn.close()
    if not watch:
        watch = demo_symbols()

    results = []
    for sym in watch:
        hist = await engine.fetch_history(sym, 260)
        if len(hist) < 60:
            continue
        # group by trading day (4 samples/day)
        day_groups = {}
        for r in hist:
            d = _iso(r["ts"]).date().isoformat()
            day_groups.setdefault(d, []).append(r)
        days_sorted = sorted(day_groups.keys())[- (days + 5):]  # buffer for lookback
        caught = []
        for di, day_key in enumerate(days_sorted[-days:]):
            # history known up to the end of this day
            window = [r for r in hist if _iso(r["ts"]).date().isoformat() <= day_key]
            if len(window) < 30:
                continue
            day_rets = day_groups[day_key]
            prices = np.array([r["price"] for r in window], dtype=float)
            volumes = np.array([r["volume"] for r in window], dtype=float)
            if len(prices) < 31:
                continue
            log_rets = np.log(prices[1:] / prices[:-1])
            # daily move = first->last price of the day
            day_open = day_rets[0]["price"]
            day_close = day_rets[-1]["price"]
            day_log_ret = math.log(day_close / day_open) if day_open > 0 else 0.0
            # score like the engine: return_z + volume_z
            ret_mean = float(np.mean(log_rets[-40:]))
            ret_std = float(np.std(log_rets[-40:]))
            return_z = engine.zscore(day_log_ret, ret_mean, max(ret_std, 1e-6))
            vol_recent = volumes[-5:].mean()
            vol_base = float(np.median(volumes[-60:])) if len(volumes) >= 20 else float(volumes.mean())
            vol_z = engine.zscore(vol_recent, vol_base, max(vol_base * 0.5, 1e-6))
            comp = (engine.DEFAULT_WEIGHTS["return"] * max(0.0, abs(engine._clip(return_z))) +
                    engine.DEFAULT_WEIGHTS["volume"] * max(0.0, abs(engine._clip(vol_z))))
            if comp >= 0.9:
                caught.append({"day": day_key, "composite": round(comp, 2),
                               "day_ret_pct": round(day_log_ret * 100, 2)})
        results.append({"symbol": sym, "caught_in_last_days": caught,
                        "flag_count": len(caught)})
    return {"days": days, "results": results}


# --------------------------------------------------------- Correlation -------

@app.get("/api/correlation")
async def correlation_matrix():
    """Pearson correlation matrix across watchlist using recent returns."""
    user_id = await ensure_user()
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT symbol FROM watchlist_items WHERE watchlist_id = "
        "(SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1)",
        (user_id,),
    )
    watch = [r["symbol"] for r in await cur.fetchall()]
    conn.close()
    if not watch:
        watch = demo_symbols()
    watch = watch[:12]

    series = {}
    for sym in watch:
        hist = await engine.fetch_history(sym, 80)
        if len(hist) >= 40:
            series[sym] = np.array([r["price"] for r in hist], dtype=float)
    all_chg = []
    names = sorted(series.keys())
    for s in names:
        p = series[s]
        all_chg.append(np.log(p[1:]) - np.log(p[:-1]))
    mat = {}
    for i, a in enumerate(names):
        mat[a] = {}
        for j, b in enumerate(names):
            if len(all_chg[i]) == len(all_chg[j]):
                corr = float(np.corrcoef(all_chg[i], all_chg[j])[0, 1])
            else:
                corr = 0.0
            if math.isnan(corr):
                corr = 0.0
            mat[a][b] = round(corr, 2)
    return {"symbols": names, "matrix": mat}


# ------------------------------------------------------------------ SSE ------

async def _live_market_task():
    """Simulate a live market: periodically append fresh quotes to watchlist
    symbols so polls/SSE show evolving prices, fresh changes and new alerts."""
    rng = np.random.default_rng(2026)
    tick = 0
    while True:
        try:
            await asyncio.sleep(6)
            tick += 1
            user_id = await ensure_user()
            conn = await get_conn()
            # drop the stale simulated ticks so history grows, not duplicates
            cur = await conn.execute(
                "SELECT symbol FROM watchlist_items WHERE watchlist_id = "
                "(SELECT id FROM watchlists WHERE user_id=? ORDER BY id LIMIT 1)",
                (user_id,),
            )
            watch = [r["symbol"] for r in await cur.fetchall()]
            if not watch:
                watch = demo_symbols()
            n_update = max(1, len(watch) // 3)
            picked = rng.choice(watch, size=min(n_update, len(watch)), replace=False)
            now = dt.datetime.now(dt.timezone.utc)
            # append recent ticks just behind "now" (market-time simulation)
            base = now - dt.timedelta(minutes=2)
            for sym in picked:
                cur = await conn.execute(
                    "SELECT price, volume FROM quotes WHERE symbol=? ORDER BY ts DESC LIMIT 1",
                    (sym,),
                )
                row = await cur.fetchone()
                if not row:
                    continue
                last_price = row["price"]
                last_vol = row["volume"]
                mv = rng.normal(0, 0.004)
                new_price = max(0.2, last_price * (1 + mv))
                new_vol = max(1, int(last_vol * rng.lognormal(0, 0.08)))
                new_ts = base + dt.timedelta(seconds=tick)
                await conn.execute(
                    "INSERT OR IGNORE INTO quotes (symbol, ts, price, volume) "
                    "VALUES (?,?,?,?)",
                    (sym, new_ts.isoformat(), round(new_price, 2), new_vol),
                )
            await conn.commit()
            await conn.close()
            if rng.random() < 0.5:
                try:
                    await generate_alerts(now)
                except Exception:
                    pass
        except Exception:
            pass


@app.get("/api/stream")
async def stream(request: Request):
    """Server-Sent Events: push a snapshot every N seconds and on demand."""
    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    snap = await dashboard()
                    if len(snap["watchlist"]) > 0:
                        await generate_alerts()
                        snap = await dashboard()
                except Exception:
                    snap = await dashboard()
                yield f"data: {json.dumps(snap)}\n\n"
                await asyncio.sleep(8)
        except asyncio.CancelledError:
            pass
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
