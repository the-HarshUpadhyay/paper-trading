"""
services/price_refresh.py — Background scheduler: yfinance → in-memory cache → DB.

Flow every PRICE_REFRESH_INTERVAL seconds:
  1. Load all tickers from the `stocks` table.
  2. Batch-fetch via market_data.refresh_prices() in chunks of 50.
  3. Persist results to stock_price_cache for cross-restart warmup.

On startup:
  - Run schema_cache.sql to ensure the cache table exists.
  - Warm the in-memory cache from any DB rows fetched within the last hour.

Design rules:
  - Never raises — the entire loop is wrapped in try/except.
  - Never calls yfinance directly — delegates to market_data.refresh_prices().
  - Daemon thread: dies automatically when the Flask process exits.
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_BATCH_SIZE  = 50   # max tickers per yf.download() call
_BATCH_PAUSE = 2    # seconds between batches to avoid rate-limit spikes


# ── DB helpers ────────────────────────────────────────────────────────────────

def _run_schema() -> None:
    """Create stock_price_cache table if it doesn't already exist."""
    import os
    sql_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema_cache.sql")
    sql_path = os.path.normpath(sql_path)
    try:
        with open(sql_path, "r") as f:
            ddl = f.read()
        # Extract just the PL/SQL block (strip the trailing /)
        block = ddl.strip().rstrip("/").strip()
        from db.connection import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(block)
            conn.commit()
            cur.close()
            logger.info("stock_price_cache table ensured")
        finally:
            conn.close()
    except Exception as e:
        logger.warning("schema_cache.sql execution failed (may already exist): %s", e)


def _get_all_tickers() -> list[str]:
    """Return every ticker symbol stored in the stocks catalogue."""
    try:
        from db.connection import DBCursor
        with DBCursor() as cur:
            cur.execute("SELECT ticker FROM stocks ORDER BY ticker")
            rows = cur.fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.error("Failed to load tickers from stocks table: %s", e)
        return []


def _warm_from_db() -> None:
    """
    On startup: read rows from stock_price_cache (< 1 hour old) into the
    in-memory cache so the first requests don't get cold-cache misses.
    """
    try:
        from db.connection import DBCursor
        from services.cache import price_cache
        with DBCursor() as cur:
            cur.execute(
                """SELECT ticker, price, change_pct, open_price, day_high, day_low,
                          previous_close, volume, market_cap
                     FROM stock_price_cache
                    WHERE fetched_at > SYSTIMESTAMP - INTERVAL '1' HOUR"""
            )
            rows = cur.fetchall()

        count = 0
        for row in rows:
            ticker, price, change_pct, open_p, high, low, prev_close, vol, mkt_cap = row
            if not ticker:
                continue
            price_cache.set_price(ticker, {
                "price":          float(price)      if price      is not None else 0.0,
                "change_pct":     float(change_pct) if change_pct is not None else 0.0,
                "open":           float(open_p)     if open_p     is not None else 0.0,
                "day_high":       float(high)       if high       is not None else 0.0,
                "day_low":        float(low)        if low        is not None else 0.0,
                "previous_close": float(prev_close) if prev_close is not None else 0.0,
                "volume":         int(vol)          if vol        is not None else 0,
                "market_cap":     int(mkt_cap)      if mkt_cap    is not None else 0,
            })
            count += 1
        logger.info("In-memory cache warmed from DB: %d tickers", count)
    except Exception as e:
        logger.warning("DB cache warmup skipped (table may not exist yet): %s", e)


def _persist_batch_to_db(tickers: list[str]) -> None:
    """
    Write the current in-memory cache entries for these tickers into
    stock_price_cache (MERGE/upsert). Best-effort — never raises.
    """
    try:
        from db.connection import DBCursor
        from services.cache import price_cache

        rows = []
        for t in tickers:
            d = price_cache.get(t)
            if d is None:
                continue
            rows.append((
                t,
                d.get("price"),
                d.get("change_pct"),
                d.get("open"),
                d.get("day_high"),
                d.get("day_low"),
                d.get("previous_close"),
                d.get("volume"),
                d.get("market_cap"),
            ))

        if not rows:
            return

        with DBCursor(auto_commit=True) as cur:
            for row in rows:
                (ticker, price, change_pct, open_p,
                 high, low, prev_close, vol, mkt_cap) = row
                cur.execute(
                    """MERGE INTO stock_price_cache dst
                       USING (SELECT :1 AS ticker FROM dual) src
                          ON (dst.ticker = src.ticker)
                     WHEN NOT MATCHED THEN
                       INSERT (ticker, price, change_pct, open_price, day_high, day_low,
                               previous_close, volume, market_cap)
                       VALUES (:2, :3, :4, :5, :6, :7, :8, :9, :10)
                     WHEN MATCHED THEN
                       UPDATE SET price          = :11,
                                  change_pct     = :12,
                                  open_price     = :13,
                                  day_high       = :14,
                                  day_low        = :15,
                                  previous_close = :16,
                                  volume         = :17,
                                  market_cap     = :18,
                                  fetched_at     = SYSTIMESTAMP""",
                    [
                        ticker,
                        # INSERT values
                        ticker, price, change_pct, open_p,
                        high, low, prev_close, vol, mkt_cap,
                        # UPDATE values
                        price, change_pct, open_p,
                        high, low, prev_close, vol, mkt_cap,
                    ],
                )
    except Exception as e:
        logger.warning("DB price persist failed: %s", e)


# ── Main loop ─────────────────────────────────────────────────────────────────

def _run_loop() -> None:
    """
    Scheduler loop — runs for the lifetime of the process.

    Complements services/scheduler.py:
      - scheduler.py  → active tickers only, every 15 s (high frequency)
      - price_refresh → ALL catalogue tickers, every 300 s + DB persistence
    """
    from config import Config
    from services.market_data import refresh_prices

    # One-time startup tasks
    _run_schema()
    _warm_from_db()

    while True:
        try:
            tickers = _get_all_tickers()
            if tickers:
                logger.debug(
                    "Full refresh cycle: %d tickers in batches of %d",
                    len(tickers), _BATCH_SIZE,
                )
                for i in range(0, len(tickers), _BATCH_SIZE):
                    batch = tickers[i : i + _BATCH_SIZE]
                    try:
                        refresh_prices(batch)
                        _persist_batch_to_db(batch)
                    except Exception as e:
                        logger.warning("Batch %d–%d failed: %s", i, i + len(batch), e)
                    if i + _BATCH_SIZE < len(tickers):
                        time.sleep(_BATCH_PAUSE)
                logger.debug("Full refresh cycle complete (%d tickers)", len(tickers))
        except Exception as e:
            logger.error("price_refresh loop error: %s", e)

        time.sleep(Config.PRICE_REFRESH_INTERVAL)


def start_refresh_daemon() -> None:
    """Start the full-catalogue DB-backed refresh thread. Call once from app.py."""
    from config import Config
    t = threading.Thread(
        target=_run_loop,
        daemon=True,
        name="price-refresh-full",
    )
    t.start()
    logger.info(
        "Full price-refresh daemon started (interval=%ds, batch=%d)",
        Config.PRICE_REFRESH_INTERVAL, _BATCH_SIZE,
    )
