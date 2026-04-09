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
        self._snapshot_tick: int = 0

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
                    """SELECT DISTINCT ticker FROM (
                           SELECT s.ticker
                             FROM stocks s
                            WHERE s.stock_id IN (
                                  SELECT stock_id FROM holdings  WHERE quantity > 0
                                  UNION
                                  SELECT stock_id FROM watchlist
                            )
                           UNION
                           SELECT ticker FROM price_alerts WHERE is_active = 1
                       )
                       ORDER BY ticker"""
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
            logger.error("Scheduler _tick error: %s", e)

        try:
            from services.cache import price_cache
            from services.pending_order_service import check_and_fill_all
            prices = {t: price_cache.get(t) for t in self._active_tickers}
            check_and_fill_all(self._active_tickers, prices)
        except Exception as e:
            logger.error("Scheduler check_and_fill_all error: %s", e)

        try:
            from services.cache import price_cache
            from services.alert_service import check_alerts
            for ticker in self._active_tickers:
                cached = price_cache.get(ticker)
                if cached and cached.get("price"):
                    check_alerts(ticker, cached["price"])
        except Exception as e:
            logger.error("Scheduler check_alerts error: %s", e)

        # Every 24 ticks (~6 minutes) save portfolio snapshots for active users
        self._snapshot_tick += 1
        if self._snapshot_tick >= 24:
            self._snapshot_tick = 0
            self._save_periodic_snapshots()

    def _save_periodic_snapshots(self) -> None:
        """Save portfolio snapshots for all users who currently hold positions."""
        try:
            from db.connection import DBCursor
            from services.portfolio_service import PortfolioService
            svc = PortfolioService()
            with DBCursor() as cur:
                cur.execute(
                    "SELECT DISTINCT user_id FROM holdings WHERE quantity > 0"
                )
                user_ids = [r[0] for r in cur.fetchall()]
            for uid in user_ids:
                try:
                    svc.save_snapshot_after_trade(uid)
                except Exception as e:
                    logger.warning("periodic snapshot(user=%s): %s", uid, e)
        except Exception as e:
            logger.warning("_save_periodic_snapshots error: %s", e)

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
