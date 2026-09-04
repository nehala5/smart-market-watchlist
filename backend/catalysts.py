"""Catalyst & insider-activity detection.

Provides two signals that add causal context to anomaly scores:
  1. EARNINGS / known events  - "is this volatility expected (earnings day) or
     unexpected (no known catalyst)?" Unexpected moves are more meaningful.
  2. INSIDER activity (Form 4) - director/officer trades coinciding with an
     anomaly is a high-conviction, contrarian signal.

Data is seeded deterministically (we can't rely on a free API key at demo time),
but the schema mirrors real SEC EDGAR Form 4 / earnings-calendar fields so it can
be swapped for a live source.
"""
import datetime as dt
import random

MAX_RETRIES = 2


def _rand(symbol, salt):
    return random.Random(int(sum(ord(c) for c in symbol)) + salt)


def earnings_dates(symbol, n=2):
    """Return upcoming earnings dates for a symbol (deterministic schedule)."""
    r = _rand(symbol, 1000)
    today = dt.datetime.now(dt.timezone.utc).date()
    dates = set()
    # ~20% chance earnings are literally TODAY (drives the catalyst_today badge)
    if r.random() < 0.20:
        dates.add(today)
    # plus 1-2 upcoming dates
    for _ in range(2):
        dates.add(today + dt.timedelta(days=r.randint(1, 10)))
    events = []
    for d in sorted(dates):
        events.append({
            "type": "earnings",
            "date": d.isoformat(),
            "title": "Quarterly earnings",
            "expected": True,
        })
    return events


def insider_activity(symbol):
    """Recent Form-4-style insider transactions (deterministic seed)."""
    r = _rand(symbol, 2000)
    if r.random() > 0.30:
        return []
    role = r.choice(["CEO", "CFO", "Director", "President", "Chief Tech Officer"])
    transaction_code = r.choice(["P", "S", "S", "S"])  # weighted to sells
    side = "buy" if transaction_code == "P" else "sell"
    days_ago = r.randint(0, 2)
    date = (dt.datetime.now(dt.timezone.utc).date()
            - dt.timedelta(days=days_ago)).isoformat()
    shares = r.randint(500, 50000)
    return [{
        "type": "insider",
        "date": date,
        "title": f"{role} filed Form 4",
        "side": side,
        "shares": shares,
        "detail": f"{'Purchased' if side == 'buy' else 'Sold'} {shares:,} shares "
                  f"({days_ago}d ago)",
        "is_contrarian_buy": side == "buy",
    }]


def get_events(symbol):
    """Combine earnings + insider into a single event list for a symbol."""
    events = []
    events.extend(earnings_dates(symbol))
    events.extend(insider_activity(symbol))
    # keep the most recent/relevant first
    events.sort(key=lambda e: e["date"], reverse=True)
    return events


def has_catalyst_today(symbol, now=None):
    """True if any known catalyst (earnings/filing/insider) coincides with now."""
    now = now or dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    for e in get_events(symbol):
        if e["date"] == today:
            return True
    return False
