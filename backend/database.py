"""Database layer: SQLite schema, connection, and CRUD helpers."""
import aiosqlite
import datetime as dt
from pathlib import Path

DB_PATH = Path(__file__).parent / "signalwatch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    market_cap FLOAT NOT NULL DEFAULT 0
);

-- Price/quote snapshots (time series)
CREATE TABLE IF NOT EXISTS quotes (
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,            -- ISO UTC
    price REAL NOT NULL,
    volume INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    bid REAL,
    ask REAL,
    PRIMARY KEY (symbol, ts)
);

CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT 'Default',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (watchlist_id, symbol)
);

-- Alert lifecycle: fired -> seen -> acknowledged -> dismissed
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    composite_score REAL NOT NULL DEFAULT 0,
    headline TEXT NOT NULL,
    signals_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'fired',
    created_at TEXT NOT NULL,
    seen_at TEXT,
    acknowledged_at TEXT,
    dismissed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_user_status ON alerts(user_id, status);

-- Per-user per-stock preferences
CREATE TABLE IF NOT EXISTS stock_prefs (
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    interest_level TEXT NOT NULL DEFAULT 'normal',  -- low / normal / high
    threshold_override REAL,
    muted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, symbol)
);
"""


async def init_db():
    conn = await aiosqlite.connect(DB_PATH)
    await conn.executescript(SCHEMA)
    await conn.commit()
    await conn.close()


async def get_conn():
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def ensure_user() -> int:
    conn = await get_conn()
    cur = await conn.execute(
        "SELECT id FROM users ORDER BY id LIMIT 1"
    )
    row = await cur.fetchone()
    if row is None:
        cur = await conn.execute(
            "INSERT INTO users (created_at) VALUES (?)",
            (dt.datetime.utcnow().isoformat(),),
        )
        await conn.commit()
        user_id = cur.lastrowid
    else:
        user_id = row["id"]
    await conn.close()
    return user_id
