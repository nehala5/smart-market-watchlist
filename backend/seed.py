"""Seed the database with a diverse universe of stocks and realistic history."""
import numpy as np
import datetime as dt
import asyncio
from database import get_conn, ensure_user
import math

# symbol -> (name, sector, base_price, annual_vol, drift)
UNIVERSE = [
    # Tech
    ("AAPL", "Apple", "Technology", 190, 0.28, 0.15),
    ("MSFT", "Microsoft", "Technology", 410, 0.24, 0.14),
    ("GOOGL", "Alphabet", "Technology", 175, 0.30, 0.12),
    ("NVDA", "NVIDIA", "Technology", 120, 0.55, 0.35),
    ("META", "Meta Platforms", "Technology", 520, 0.36, 0.18),
    ("AMZN", "Amazon", "Consumer", 185, 0.30, 0.10),
    ("TSLA", "Tesla", "Consumer", 260, 0.55, 0.05),
    ("NFLX", "Netflix", "Communication", 650, 0.35, 0.15),
    ("AMD", "Advanced Micro Devices", "Technology", 165, 0.48, 0.22),
    ("INTC", "Intel", "Technology", 34, 0.40, -0.05),
    ("CRM", "Salesforce", "Technology", 300, 0.32, 0.10),
    ("ORCL", "Oracle", "Technology", 135, 0.28, 0.12),
    ("ADBE", "Adobe", "Technology", 520, 0.30, 0.08),
    ("CSCO", "Cisco", "Technology", 50, 0.22, 0.03),
    ("QCOM", "Qualcomm", "Technology", 145, 0.34, 0.10),
    # Financials
    ("JPM", "JPMorgan Chase", "Financials", 200, 0.22, 0.10),
    ("BAC", "Bank of America", "Financials", 40, 0.24, 0.08),
    ("GS", "Goldman Sachs", "Financials", 470, 0.28, 0.12),
    ("V", "Visa", "Financials", 285, 0.20, 0.12),
    ("MA", "Mastercard", "Financials", 480, 0.20, 0.12),
    ("PYPL", "PayPal", "Financials", 65, 0.34, 0.05),
    ("AXP", "American Express", "Financials", 260, 0.24, 0.10),
    # Healthcare
    ("JNJ", "Johnson & Johnson", "Healthcare", 155, 0.12, 0.02),
    ("PFE", "Pfizer", "Healthcare", 28, 0.20, -0.02),
    ("LLY", "Eli Lilly", "Healthcare", 900, 0.28, 0.20),
    ("UNH", "UnitedHealth", "Healthcare", 490, 0.20, 0.08),
    ("MRK", "Merck", "Healthcare", 120, 0.18, 0.04),
    ("ABBV", "AbbVie", "Healthcare", 175, 0.18, 0.06),
    # Consumer
    ("KO", "Coca-Cola", "Consumer", 62, 0.14, 0.05),
    ("PEP", "PepsiCo", "Consumer", 175, 0.14, 0.04),
    ("WMT", "Walmart", "Consumer", 175, 0.18, 0.08),
    ("COST", "Costco", "Consumer", 760, 0.20, 0.12),
    ("MCD", "McDonald's", "Consumer", 250, 0.18, 0.05),
    ("NKE", "Nike", "Consumer", 95, 0.26, 0.00),
    ("SBUX", "Starbucks", "Consumer", 90, 0.28, 0.02),
    # Energy / Industrials
    ("XOM", "Exxon Mobil", "Energy", 110, 0.22, 0.04),
    ("CVX", "Chevron", "Energy", 155, 0.22, 0.03),
    ("CAT", "Caterpillar", "Industrials", 370, 0.24, 0.10),
    ("BA", "Boeing", "Industrials", 230, 0.32, 0.03),
    ("GE", "GE Aerospace", "Industrials", 175, 0.28, 0.12),
    ("UPS", "UPS", "Industrials", 130, 0.22, 0.00),
    # Communication
    ("DIS", "Disney", "Communication", 110, 0.30, 0.06),
    ("CMCSA", "Comcast", "Communication", 42, 0.22, 0.03),
    ("T", "AT&T", "Communication", 20, 0.18, 0.02),
    ("TMUS", "T-Mobile", "Communication", 175, 0.22, 0.10),
]

SECTORS = {
    "Technology", "Financials", "Healthcare", "Consumer",
    "Energy", "Industrials", "Communication",
}

# Stock symbols that carry high weight in market (for VIX-like macro sim)
BETA_MARKET = {  # beta to S&P-500-like factor
    "AAPL": 1.2, "MSFT": 1.1, "GOOGL": 1.1, "NVDA": 1.9, "META": 1.5,
    "AMZN": 1.3, "TSLA": 2.0, "NFLX": 1.4, "AMD": 1.8, "INTC": 1.5,
    "JPM": 1.1, "BAC": 1.1, "GS": 1.2, "V": 0.9, "MA": 0.9, "PYPL": 1.4,
    "JNJ": 0.5, "PFE": 0.4, "LLY": 0.6, "KO": 0.5, "WMT": 0.6, "XOM": 0.8, "CVX": 0.8,
    "CAT": 1.2, "BA": 1.5, "GE": 1.1, "DIS": 1.3, "T": 0.6,
}


def seeded_rng(symbol: str, base_seed: int = 42) -> np.random.Generator:
    seed = int(base_seed + sum(ord(c) for c in symbol))
    return np.random.default_rng(seed)


def generate_history(symbol, base, annual_vol, drift, days=260, samples_per_day=4):
    """Generate a geometric random walk over `days` trading days.

    Returns a list of (ts_iso, price, volume). Uses LOG returns so prices stay
    positive-stable, and injects occasional idiosyncratic news shocks and volume
    spikes so the anomaly engine has genuinely unusual days to flag. A shared
    market factor creates cross-sectional correlation for the correlation signal.
    """
    rng = seeded_rng(symbol)
    idio_daily = annual_vol / math.sqrt(252)        # idiosyncratic per-day vol
    drift_daily = drift / 252
    beta = BETA_MARKET.get(symbol, 1.0)
    market_daily = 0.00035                            # calm market drift
    market_rng = np.random.default_rng(1234)          # shared market factor RNG
    market_vol_daily = 0.012

    series = []
    price = base
    for d in range(days):
        date = dt.datetime.utcnow().date() - dt.timedelta(days=days - d)
        if date.weekday() >= 5:
            continue
        mkt = market_rng.normal(market_daily, market_vol_daily)
        day_ret_log = drift_daily + beta * mkt + rng.normal(0, idio_daily)
        # ~6% of days get a news shock (bigger move + strong volume surge)
        shock = 0.0
        vol_surge = 1.0
        if rng.random() < 0.06:
            shock = rng.normal(0, idio_daily * 2.1)
            day_ret_log += shock
            vol_surge = rng.uniform(2.2, 6.0)
        # base of the day
        day_base = price
        for s in range(samples_per_day):
            # distribute the day's log return across the intraday samples
            frac = (s + 1) / samples_per_day
            target_log = day_ret_log * frac - day_ret_log * (s) / samples_per_day
            # cumulative-true: apply incremental portion
            prev_log = day_ret_log * (s) / samples_per_day
            step_log = target_log - prev_log
            price = max(0.2, price * math.exp(step_log))
            base_vol = 500_000 + rng.poisson(200_000)
            vol_mult = vol_surge  # surge applies across the shock day
            # occasional unrelated volume pop
            if rng.random() < 0.015:
                vol_mult *= rng.uniform(2.5, 5)
            ts = dt.datetime.combine(date, dt.time(9, 30)) + dt.timedelta(
                minutes=int(390 * (s + 1) / samples_per_day)
            )
            ts = ts.replace(tzinfo=dt.timezone.utc)
            series.append((ts.isoformat(), round(price, 2), int(base_vol * vol_mult)))
    return series


async def seed():
    await ensure_user()
    conn = await get_conn()
    await conn.executemany(
        "INSERT OR REPLACE INTO stocks (symbol, name, sector, market_cap) "
        "VALUES (?,?,?,?)",
        [(s, n, sec, round(base * 1e9, 2))
         for s, n, sec, base, _, _ in UNIVERSE],
    )
    # Clear old market data so reseeding is idempotent (no duplicate timelines)
    await conn.execute("DELETE FROM quotes")
    await conn.execute("DELETE FROM alerts")
    total = 0
    for symbol, name, sec, base, vol, drift in UNIVERSE:
        series = generate_history(symbol, base, vol, drift)
        await conn.executemany(
            "INSERT OR IGNORE INTO quotes (symbol, ts, price, volume) VALUES (?,?,?,?)",
            [(symbol, ts, p, v) for ts, p, v in series],
        )
        total += len(series)
    await conn.commit()
    await conn.close()
    print(f"Seeded {len(UNIVERSE)} stocks, {total} quote samples")


if __name__ == "__main__":
    asyncio.run(seed())
