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
  - Call notify_ticker_added(ticker) after any add/buy event to register the
    ticker immediately (prices available within the next 15 s tick) rather than
    waiting up to TICKER_REFRESH_INTERVAL seconds for the next DB reload
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

    After adding a ticker to the watchlist or executing a buy, call:
        from services.scheduler import notify_ticker_added
        notify_ticker_added(ticker)
    This ensures the ticker is fetched on the very next price-refresh tick
    (~15 s) instead of waiting for the DB reload interval (~60 s).
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_tickers: list[str] = []
        self._last_ticker_refresh: float = 0.0
        self._lock = threading.Lock()  # guards _active_tickers

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

    def notify_ticker_added(self, ticker: str) -> None:
        """
        Immediately register *ticker* in the active set so it is included in
        the next price-refresh tick (≤ PRICE_REFRESH_INTERVAL seconds away).

        Call this after:
          - A user adds a stock to the watchlist
          - A user executes a BUY order
          - Any other event that introduces a new ticker to track

        This avoids the up-to-TICKER_REFRESH_INTERVAL second delay before the
        next full DB reload picks up the new ticker.  The DB reload still runs
        on its normal schedule and will include the ticker automatically, so
        there is no risk of the ticker being silently dropped.
        """
        ticker = ticker.upper()
        with self._lock:
            if ticker not in self._active_tickers:
                self._active_tickers.append(ticker)
                logger.debug(
                    "PriceScheduler: ticker %s registered immediately (will fetch on next tick)",
                    ticker,
                )

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
            new_tickers = self._load_active_tickers()
            with self._lock:
                self._active_tickers = new_tickers
            self._last_ticker_refresh = now

        with self._lock:
            active = list(self._active_tickers)

        if not active:
            return

        try:
            refresh_prices(active)
        except Exception as e:
            logger.error("Scheduler _tick error: %s", e)

        try:
            from services.cache import price_cache
            from services.pending_order_service import check_and_fill_all
            prices = {t: price_cache.get(t) for t in active}
            check_and_fill_all(active, prices)
        except Exception as e:
            logger.error("Scheduler check_and_fill_all error: %s", e)

        try:
            from services.cache import price_cache
            from services.alert_service import check_alerts
            for ticker in active:
                cached = price_cache.get(ticker)
                if cached and cached.get("price"):
                    check_alerts(ticker, cached["price"])
        except Exception as e:
            logger.error("Scheduler check_alerts error: %s", e)

    def _run_loop(self) -> None:
        """Main loop — runs until stop() sets the event."""
        logger.info("PriceScheduler loop entered")

        # Prime the ticker list before the first sleep
        initial = self._load_active_tickers()
        with self._lock:
            self._active_tickers = initial
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


def notify_ticker_added(ticker: str) -> None:
    """
    Immediately register *ticker* in the scheduler's active set.

    Call this after watchlist-add or buy events so the new ticker is fetched
    on the next tick (within PRICE_REFRESH_INTERVAL seconds) rather than
    waiting for the next full DB reload (TICKER_REFRESH_INTERVAL seconds).

    Example (in a route handler after a successful watchlist add)::

        from services.scheduler import notify_ticker_added
        notify_ticker_added(ticker)
    """
    _scheduler.notify_ticker_added(ticker)
