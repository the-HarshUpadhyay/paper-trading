"""
services/cache.py — Thread-safe in-memory price cache with TTL.

Single process, module-level singleton. All services share the same cache
instance so one scheduler refresh benefits every concurrent request.

TTLs:
  PRICE_TTL  = 30s  — how long basic price/change_pct data stays fresh
  QUOTE_TTL  = 60s  — how long a full quote (with fundamentals) stays fresh

⚠️  MULTI-PROCESS LIMITATION
------------------------------
This cache is **process-local**.  When the backend runs with a multi-worker
WSGI server (e.g. ``gunicorn --workers N`` with N > 1), each worker holds
its own independent copy of the cache.  This means:

  * Different workers may return different prices for the same ticker until
    every worker's background scheduler has refreshed independently.
  * Pending-order trigger checks run per-worker, so the same order could
    (extremely rarely) be evaluated twice on two workers in the same tick.

**For single-process deployments** (``python app.py``, ``gunicorn -w 1``)
this is entirely safe and correct.

**To support multi-process deployments**, replace the in-memory dict with a
Redis-backed backend:
  1.  Install ``redis`` and ``flask-caching`` (or use ``redis-py`` directly).
  2.  Replace ``PriceCache._data`` with ``redis.StrictRedis`` hash operations.
  3.  The public interface (``get``, ``set_price``, ``set_quote``, ...)
      should remain unchanged to minimise callsite updates.
  4.  Move the ``_in_progress`` deduplication set to a Redis SET with a TTL.

Until then, run the backend as a single gunicorn worker to avoid cache drift.
"""
from __future__ import annotations

import threading
import time

# Staleness thresholds (seconds)
PRICE_TTL = 30
QUOTE_TTL = 60


class PriceCache:
    """
    Thread-safe in-memory store for stock data.

    Each entry is a plain dict that may contain:
      price, change_pct, company_name, sector, exchange — from batch fetch
      pe_ratio, market_cap, day_high, … — added by full-quote fetch

    Two optional timestamp fields track freshness:
      price_ts  — set whenever price/change_pct are written
      quote_ts  — set when a full-quote fetch writes the complete payload

    In-progress set prevents duplicate simultaneous fetches for the same ticker.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._in_progress: set[str] = set()

    # ── Read ───────────────────────────────────────────────────────────────

    def get(self, ticker: str) -> dict | None:
        with self._lock:
            return self._data.get(ticker.upper())

    def price_is_stale(self, ticker: str) -> bool:
        """True if basic price data is missing or older than PRICE_TTL."""
        with self._lock:
            entry = self._data.get(ticker.upper())
            if entry is None:
                return True
            return (time.time() - entry.get("price_ts", 0)) > PRICE_TTL

    def quote_is_stale(self, ticker: str) -> bool:
        """True if full quote data is missing or older than QUOTE_TTL."""
        with self._lock:
            entry = self._data.get(ticker.upper())
            if entry is None:
                return True
            return (time.time() - entry.get("quote_ts", 0)) > QUOTE_TTL

    def has_full_quote(self, ticker: str) -> bool:
        """True if a full-quote fetch has been performed for this ticker."""
        with self._lock:
            entry = self._data.get(ticker.upper())
            return bool(entry and entry.get("quote_ts"))

    # ── Write ──────────────────────────────────────────────────────────────

    def set_price(self, ticker: str, price_data: dict) -> None:
        """Merge basic price/change_pct data into the cached entry."""
        ticker = ticker.upper()
        with self._lock:
            entry = self._data.setdefault(ticker, {})
            entry.update(price_data)
            entry["price_ts"] = time.time()
            entry["ticker"] = ticker

    def set_quote(self, ticker: str, quote_data: dict) -> None:
        """Merge full quote data into the cached entry, marking both timestamps."""
        ticker = ticker.upper()
        with self._lock:
            entry = self._data.setdefault(ticker, {})
            entry.update(quote_data)
            now = time.time()
            entry["price_ts"] = now
            entry["quote_ts"] = now
            entry["ticker"] = ticker

    # ── Deduplication ──────────────────────────────────────────────────────

    def mark_in_progress(self, ticker: str) -> bool:
        """
        Atomically claim this ticker for fetching.
        Returns True if successfully claimed; False if already in flight.
        """
        ticker = ticker.upper()
        with self._lock:
            if ticker in self._in_progress:
                return False
            self._in_progress.add(ticker)
            return True

    def unmark_in_progress(self, ticker: str) -> None:
        with self._lock:
            self._in_progress.discard(ticker.upper())

    def is_in_progress(self, ticker: str) -> bool:
        with self._lock:
            return ticker.upper() in self._in_progress

    # ── Introspection ──────────────────────────────────────────────────────

    def all_tickers(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._data)


# Module-level singleton shared across all services
price_cache = PriceCache()
