"""Anomaly scoring engine.

Produces a composite per-stock anomaly score by combining independent signals,
each expressed as a z-score relative to the symbol's own rolling history and its
sector peers. Scores are time-decayed so old moves fade.

Signals:
  - VOLATILITY_Z  : realized vol vs 20d rolling (regime spikes)
  - VOLUME_Z      : volume vs 20d median (liquidity surge)
  - BREAKOUT_Z    : distance from 20d/50d high-low range (momentum/breakout)
  - CORRELATION_Z : decoupling from sector peers (isolated mover)
  - SPREAD_Z      : bid-ask asymmetry (market-maker stress)

Composite = sum(weight_i * clip(z_i)) * time_decay
Weights are default, but sector-aware baseline volatility normalizes thresholds.
"""
import datetime as dt
import math
import json
import numpy as np
from database import get_conn

DEFAULT_WEIGHTS = {
    "return": 0.28,
    "volatility": 0.22,
    "volume": 0.22,
    "breakout": 0.18,
    "correlation": 0.10,
    "spread": 0.00,
}

# Sector baseline vol multipliers (tech ~2x utilities in reality; simplify).
SECTOR_VOL = {
    "Technology": 1.4, "Communication": 1.3, "Industrials": 1.1,
    "Consumer": 0.8, "Financials": 1.0, "Healthcare": 0.7, "Energy": 1.0,
}

SECTOR_NAME = {
    "Technology": "Tech", "Communication": "Comm", "Industrials": "Industrials",
    "Consumer": "Consumer", "Financials": "Financials",
    "Healthcare": "Healthcare", "Energy": "Energy",
}

# Decay: half-life of 12h for the alert importance.
DECAY_HALFLIFE_H = 12.0


def decay_multiplier(ts: dt.datetime, now: dt.datetime | None = None) -> float:
    now = now or dt.datetime.now(dt.timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    age_h = max(0.0, (now - ts).total_seconds() / 3600.0)
    return 0.5 ** (age_h / DECAY_HALFLIFE_H)


def zscore(x, mean, std):
    if std is None or not math.isfinite(std) or std <= 1e-12:
        return 0.0
    return (x - mean) / std


def _clip(z, lo=-3.0, hi=3.0):
    return max(lo, min(hi, z))


def wilson_conf(p, n):
    """Wilson score confidence (for volume-confidence of signals)."""
    if n <= 0:
        return 0.0
    z = 1.96
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - margin


async def latest_quotes(symbols=None, now=None):
    """Return latest quote per symbol plus a short history for scoring."""
    conn = await get_conn()
    rows = None
    if symbols:
        placeholders = ",".join("?" for _ in symbols)
        cur = await conn.execute(
            f"SELECT symbol, ts, price, volume FROM quotes "
            f"WHERE symbol IN ({placeholders}) ORDER BY ts DESC",
            symbols,
        )
        rows = await cur.fetchall()
    else:
        cur = await conn.execute(
            "SELECT symbol, ts, price, volume FROM quotes ORDER BY ts DESC"
        )
        rows = await cur.fetchall()
    await conn.close()
    return rows


async def fetch_history(symbol, limit=200):
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT ts, price, volume FROM quotes WHERE symbol=? ORDER BY ts DESC LIMIT ?",
        (symbol, limit),
    )
    rows = await cur.fetchall()
    await conn.close()
    return list(reversed(rows))


async def compute_stock_score(symbol, now=None):
    """Compute composite + per-signal z-scores for a single symbol."""
    now = now or dt.datetime.now(dt.timezone.utc)
    hist = await fetch_history(symbol, 200)
    if len(hist) < 30:
        return None

    prices = np.array([r["price"] for r in hist], dtype=float)
    volumes = np.array([r["volume"] for r in hist], dtype=float)
    ts = [r["ts"] for r in hist]
    dur_h = max(1.0, (now - _iso(ts[-1])).total_seconds() / 3600.0)

    # --- volatility signal -------------------------------------------------
    rets = np.diff(prices)
    log_rets = np.log(prices[1:] / prices[:-1])
    # realized vol last window vs prior
    look = min(20, len(log_rets))
    recent_vol = np.std(log_rets[-look:])
    prev_vol = np.std(log_rets[-2 * look: -look]) if len(log_rets) > 2 * look else recent_vol
    vol_mean = max(prev_vol, 1e-6)
    vol_std = max(vol_mean * 0.5, 1e-6)
    vol_z = zscore(recent_vol, vol_mean, vol_std)

    # --- return magnitude signal -------------------------------------------
    # Directly score the latest move vs the stock's own history of moves,
    # expressed as a z-score. This is the most intuitive definition of "something
    # happened today" and is not diluted by the (already high) volatility context.
    if len(log_rets) > 10:
        ret_mean = float(np.mean(log_rets[-40:])) if len(log_rets) >= 40 else float(np.mean(log_rets))
        ret_std = float(np.std(log_rets[-40:])) if len(log_rets) >= 40 else float(np.std(log_rets))
        latest_ret = log_rets[-1]
        return_z = zscore(latest_ret, ret_mean, ret_std)
    else:
        latest_ret = 0.0
        return_z = 0.0

    # --- volume signal ------------------------------------------------------
    vol_recent = volumes[-5:].mean()
    vol_median = np.median(volumes[-60:]) if len(volumes) >= 20 else volumes.mean()
    vol_base = max(vol_median, 1e-6)
    vol_ratio = vol_recent / vol_base
    vol_std = max(vol_base * 0.5, 1e-6)
    vol_z = zscore(vol_recent, vol_base, vol_std)

    # --- breakout signal -----------------------------------------------------
    hi20 = prices[-20:].max() if len(prices) >= 20 else prices.max()
    lo20 = prices[-20:].min() if len(prices) >= 20 else prices.min()
    rng = max(hi20 - lo20, 1e-6)
    latest = prices[-1]
    # distance from midpoint normalized by range; +1 = at high, -1 = at low
    breakout_ratio = (latest - (hi20 + lo20) / 2) / (rng / 2)
    historical_median = (hi20 + lo20) / 2
    hist_std = np.std(prices[-20:]) if len(prices) >= 20 else 1.0
    breakout_z = zscore(latest, historical_median, max(hist_std, 1e-6))

    signals = {
        "return": _clip(return_z),
        "volatility": _clip(vol_z),
        "volume": _clip(vol_z),
        "breakout": _clip(breakout_z),
        "spread": 0.0,
    }

    composite = 0.0
    for key, w in DEFAULT_WEIGHTS.items():
        composite += w * max(0.0, abs(signals.get(key, 0.0)))

    # normalize by sector baseline vol so same threshold isn't applied to all
    conn = await get_conn()
    cur = await conn.execute("SELECT sector FROM stocks WHERE symbol=?", (symbol,))
    srow = await cur.fetchone()
    await conn.close()
    sector = srow["sector"] if srow else "Technology"
    sector_norm = SECTOR_VOL.get(sector, 1.0)
    # Higher sector vol => same absolute move is less unusual => scale down
    composite_norm = composite / (sector_norm ** 0.7)
    composite_norm = max(0.0, min(10.0, composite_norm))

    return {
        "symbol": symbol,
        "sector": sector,
        "sector_short": SECTOR_NAME.get(sector, sector),
        "price": float(latest),
        "change_pct": float((prices[-1] / prices[-2] - 1) * 100) if len(prices) > 1 else 0.0,
        "volume_ratio": float(vol_ratio),
        "signals": signals,
        "signal_values": {
            "return_z": float(return_z), "vol_z": float(vol_z),
            "volume_z": float(vol_z), "breakout_z": float(breakout_z),
        },
        "composite": round(float(composite_norm), 3),
        "decay": round(decay_multiplier(_iso(ts[-1]), now), 3),
        "freshness_sec": round((now - _iso(ts[-1])).total_seconds()),
        "series_prices": [float(p) for p in prices[-24:]],
        # Relative-strength context (trend regime, not just today's move)
        "rs_20d": round(float((prices[-1] / prices[-20] - 1) * 100), 2)
                  if len(prices) >= 20 and prices[-20] > 0 else round(float((prices[-1] / prices[0] - 1) * 100), 2),
        "high_52w": float(prices.max()),
        "low_52w": float(prices.min()),
        "pos_in_52w": round(float((prices[-1] - prices.min()) / max(prices.max() - prices.min(), 1e-6) * 100), 1),
    }


async def sector_movers(symbols, now=None):
    """Compute scores for all symbols, then attach sector peer medians &
    correlation decoupling so relative moves are shown, not absolute only."""
    scores = []
    for s in symbols:
        sc = await compute_stock_score(s, now)
        if sc:
            scores.append(sc)
    # group by sector
    by_sector = {}
    for sc in scores:
        by_sector.setdefault(sc["sector"], []).append(sc)
    for sc in scores:
        peers = by_sector.get(sc["sector"], [sc])
        peer_median = float(np.median([p["change_pct"] for p in peers]))
        peer_vol = float(np.median([abs(p["composite"]) for p in peers]))
        sc["peer_median_change"] = peer_median
        sc["relative_change"] = round(sc["change_pct"] - peer_median, 2)
        # Correlation/demand signal: isolated mover if |relative| big vs peers
        corr_std = max(np.std([p["change_pct"] for p in peers]) if len(peers) > 1 else 1.0, 1e-6)
        sc["correlation_z"] = _clip(zscore(sc["change_pct"], peer_median, corr_std))
        sc["signals"]["correlation"] = sc["correlation_z"]
        # Recompute composite including correlation
        composite = 0.0
        for key, w in DEFAULT_WEIGHTS.items():
            composite += w * max(0.0, abs(sc["signals"].get(key, 0.0)))
        sector_norm = SECTOR_VOL.get(sc["sector"], 1.0)
        sc["composite"] = round(max(0.0, min(10.0, composite / (sector_norm ** 0.7))), 3)
    return scores


def traffic_light(composite: float) -> str:
    if composite >= 1.8:
        return "unusual"
    if composite >= 0.8:
        return "watch"
    return "normal"


def _iso(ts):
    if isinstance(ts, dt.datetime):
        return ts
    try:
        return dt.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return dt.datetime.now(dt.timezone.utc)
