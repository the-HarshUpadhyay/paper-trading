"""
services/scheduler.py — Background price refresh scheduler.

Runs a single daemon thread that periodically:
  1. Queries the DB for "active" tickers (held in any portfolio or watchlist)
  2. Batch-fetches their prices from yfinance via market_data.refresh_prices()
  3. Writes results into the in-memory cache

Design guarantees:
  - No yfinance call ever originates from a request handler
  - Scheduler errors are logged and swallowed — it NEVER crashes
  - Stopping is clean: the loop checks an Event every second
  - Active ticker list is refreshed from DB every TICKER_REFRESH_INTERVAL seconds
    so new watchlist / portfolio additions are picked up automatically
"""
from __future__ import annotations

import logging
import threading
import time

from db.connection import DBCursor
from services.market_data import refresh_prices

logger = logging.getLogger(__name__)

# How often to push prices into the cache (seconds)
PRICE_REFRESH_INTERVAL = 15

# How often to re-query active tickers from the database (seconds)
TICKER_REFRESH_INTERVAL = 60


class PriceScheduler:
    """
    Daemon thread scheduler for background price refreshes.

    Usage (from app.py):
        from services.scheduler import start_scheduler, stop_scheduler
        start_scheduler()          # call once at app startup
        ...
        stop_scheduler()           # call on SIGTERM / app teardown
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_tickers: list[str] = []
        self._last_ticker_refresh: float = 0.0

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background thread. Safe to call multiple times."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="PriceScheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "PriceScheduler started — price refresh every %ds, "
            "ticker list refresh every %ds",
            PRICE_REFRESH_INTERVAL,
            TICKER_REFRESH_INTERVAL,
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the thread to stop and wait up to *timeout* seconds."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("PriceScheduler stopped")

    # ── Internal helpers ───────────────────────────────────────────────────

    def _load_active_tickers(self) -> list[str]:
        """
        Return tickers that are actively held in a portfolio or on a watchlist.
        Falls back to the last known list if the DB query fails.
        """
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT DISTINCT s.ticker
                         FROM stocks s
                        WHERE s.stock_id IN (
                              SELECT stock_id FROM holdings  WHERE quantity > 0
                              UNION
                              SELECT stock_id FROM watchlist
                        )
                        ORDER BY s.ticker"""
                )
                rows = cur.fetchall()
            tickers = [row[0] for row in rows]
            logger.debug("Active tickers reloaded: %d stocks", len(tickers))
            return tickers
        except Exception as e:
            logger.warning("Could not load active tickers from DB: %s", e)
            return self._active_tickers   # Keep using previous list

    def _tick(self) -> None:
        """
        One refresh cycle:
          1. Re-load active tickers if the list is stale.
          2. Batch-refresh prices for all active tickers.
        """
        now = time.time()

        # Refresh the ticker list when due
        if (now - self._last_ticker_refresh) >= TICKER_REFRESH_INTERVAL:
            self._active_tickers = self._load_active_tickers()
            self._last_ticker_refresh = now

        if not self._active_tickers:
            return

        try:
            refresh_prices(self._active_tickers)
        except Exception as e:
            # refresh_prices already swallows errors, but guard here too
            logger.error("Scheduler _tick error: %s", e)

    def _run_loop(self) -> None:
        """Main loop — runs until stop() sets the event."""
        logger.info("PriceScheduler loop entered")

        # Prime the ticker list before the first sleep
        self._active_tickers = self._load_active_tickers()
        self._last_ticker_refresh = time.time()

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error("Unexpected scheduler loop error (continuing): %s", e)

            # Sleep in 1-second increments so stop() is responsive
            for _ in range(PRICE_REFRESH_INTERVAL):
                if self._stop_event.is_set():
                    break
                time.sleep(1)


# ── Module-level singleton ────────────────────────────────────────────────────

_scheduler = PriceScheduler()


def start_scheduler() -> None:
    """Start the global scheduler. Idempotent."""
    _scheduler.start()


def stop_scheduler() -> None:
    """Stop the global scheduler cleanly."""
    _scheduler.stop()
