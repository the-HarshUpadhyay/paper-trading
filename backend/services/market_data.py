"""
services/market_data.py — Unified market data layer.

Architecture:
    Scheduler ──► yfinance ──► market_data ──► price_cache ──► API services
                                  ↑
                          Only entry point to yfinance.
                          API services NEVER call yfinance directly.

Public surface for other services:
  sanitize_stock_data(data)     — replace None with safe defaults
  should_refresh(ts, max_age)   — staleness predicate
  get_price(ticker)             — read-through for a single ticker
  get_batch_prices(tickers)     — read-through for many tickers
  refresh_prices(tickers)       — force cache population (called by scheduler)
  refresh_quote(ticker)         — force full-quote cache update
"""
from __future__ import annotations

import logging
import threading

import pandas as pd
import yfinance as yf

from services.cache import price_cache, PRICE_TTL, QUOTE_TTL

logger = logging.getLogger(__name__)


# ── Safe defaults ─────────────────────────────────────────────────────────────
# Every field that might be None in a raw yfinance response has a typed default.
# Applied by sanitize_stock_data() before any data leaves this layer.

_PRICE_DEFAULTS: dict = {
    "price":          0.0,
    "change_pct":     0.0,
}

_QUOTE_DEFAULTS: dict = {
    "price":          0.0,
    "change_pct":     0.0,
    "open":           0.0,
    "day_high":       0.0,
    "day_low":        0.0,
    "previous_close": 0.0,
    "volume":         0,
    "avg_volume":     0,
    "market_cap":     0,
    "pe_ratio":       0.0,
    "52w_high":       0.0,
    "52w_low":        0.0,
    "company_name":   "N/A",
    "sector":         "N/A",
    "industry":       "N/A",
    "exchange":       "N/A",
    "description":    "",
}


def sanitize_stock_data(data: dict | None, full_quote: bool = False) -> dict:
    """
    Guarantee that no field is None.

    Rules applied in order:
      1. If data is None  → return a dict of all-default values
      2. For each expected key: replace None with its typed default
      3. Pass extra keys through unchanged (they can't be None or they'd
         have been caught by the relevant type's defaults above)

    Args:
        data:       raw dict from yfinance or cache (may contain Nones)
        full_quote: if True, apply the extended quote defaults as well
    """
    defaults = {**_PRICE_DEFAULTS, **(  _QUOTE_DEFAULTS if full_quote else {})}

    if data is None:
        return defaults.copy()

    result: dict = {}

    # Apply typed defaults for known keys
    for key, default in defaults.items():
        val = data.get(key)
        result[key] = default if val is None else val

    # Pass through any additional keys, converting None → ""
    for key, val in data.items():
        if key not in result:
            result[key] = val if val is not None else ""

    return result


def should_refresh(last_updated_ts: float | None, max_age: float = PRICE_TTL) -> bool:
    """Return True when data is absent or older than max_age seconds."""
    import time
    if last_updated_ts is None:
        return True
    return (time.time() - last_updated_ts) > max_age


# ── yfinance fetch helpers (internal only) ────────────────────────────────────

def _yf_batch_prices(tickers: list[str]) -> dict[str, dict]:
    """
    Download latest close prices for a list of tickers.
    Returns {ticker: {price, change_pct}}.  Never raises.
    """
    if not tickers:
        return {}

    result: dict[str, dict] = {}
    try:
        data = yf.download(
            " ".join(tickers),
            period="2d",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return result

        if isinstance(data.columns, pd.MultiIndex):
            # yfinance >= 0.2.40: columns are (field, ticker)
            for t in tickers:
                try:
                    closes = data["Close"][t].dropna()
                    if len(closes) >= 2:
                        price  = round(float(closes.iloc[-1]), 4)
                        change = round(
                            (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2
                        )
                        result[t] = {"price": price, "change_pct": change}
                    elif len(closes) == 1:
                        result[t] = {
                            "price":      round(float(closes.iloc[-1]), 4),
                            "change_pct": 0.0,
                        }
                except Exception:
                    pass
        else:
            # Single ticker — flat column names
            try:
                closes = data["Close"].dropna()
                if not closes.empty and len(tickers) == 1:
                    t = tickers[0]
                    price  = round(float(closes.iloc[-1]), 4)
                    change = 0.0
                    if len(closes) >= 2:
                        change = round(
                            (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2
                        )
                    result[t] = {"price": price, "change_pct": change}
            except Exception:
                pass

    except Exception as e:
        logger.warning("yfinance batch download failed (%s): %s", tickers, e)

    return result


def _yf_full_quote(ticker: str) -> dict | None:
    """
    Fetch the full Ticker.info dict for a single ticker.
    Returns a normalised dict or None if the ticker is invalid / unreachable.
    """
    try:
        info = yf.Ticker(ticker).info
        # info can be None or an empty/minimal dict for unknown symbols
        if not info or not isinstance(info, dict) or not info.get("symbol"):
            return None

        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        prev_close = info.get("previousClose")
        change_pct = None
        if price and prev_close:
            change_pct = round((price - prev_close) / prev_close * 100, 2)

        return {
            "ticker":         info.get("symbol", ticker),
            "company_name":   info.get("longName") or info.get("shortName") or ticker,
            "sector":         info.get("sector") or "",
            "industry":       info.get("industry") or "",
            "exchange":       info.get("exchange") or "",
            "price":          price,
            "open":           info.get("open") or info.get("regularMarketOpen"),
            "day_high":       info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "day_low":        info.get("dayLow") or info.get("regularMarketDayLow"),
            "previous_close": prev_close,
            "volume":         info.get("volume") or info.get("regularMarketVolume"),
            "market_cap":     info.get("marketCap"),
            "pe_ratio":       info.get("trailingPE"),
            "52w_high":       info.get("fiftyTwoWeekHigh"),
            "52w_low":        info.get("fiftyTwoWeekLow"),
            "avg_volume":     info.get("averageVolume"),
            "description":    info.get("longBusinessSummary") or "",
            "change_pct":     change_pct,
        }
    except Exception as e:
        logger.warning("yfinance full quote failed (%s): %s", ticker, e)
        return None


# ── Cache population (called by scheduler + on-demand) ───────────────────────

def refresh_prices(tickers: list[str]) -> None:
    """
    Batch-fetch prices from yfinance and write to cache.

    Uses in-progress markers to prevent duplicate concurrent fetches.
    Errors are logged but never raised — caller is always safe.
    """
    if not tickers:
        return

    # Claim only tickers not already being fetched
    to_fetch = [t for t in tickers if price_cache.mark_in_progress(t)]
    if not to_fetch:
        return

    try:
        fetched = _yf_batch_prices(to_fetch)
        for ticker, data in fetched.items():
            price_cache.set_price(ticker, data)
        if fetched:
            logger.debug("Cache updated for %d tickers", len(fetched))
    except Exception as e:
        logger.error("refresh_prices unexpected error: %s", e)
    finally:
        for t in to_fetch:
            price_cache.unmark_in_progress(t)


def refresh_quote(ticker: str) -> None:
    """
    Fetch full Ticker.info and write to cache.
    Used for the stock detail endpoint and as a fallback on cache miss.
    """
    if not price_cache.mark_in_progress(ticker):
        return  # Another thread is already fetching this ticker

    try:
        data = _yf_full_quote(ticker)
        if data:
            price_cache.set_quote(ticker, data)
            logger.debug("Full quote cached for %s", ticker)
    except Exception as e:
        logger.error("refresh_quote(%s) unexpected error: %s", ticker, e)
    finally:
        price_cache.unmark_in_progress(ticker)


# ── Public read-through API ───────────────────────────────────────────────────

def get_price(ticker: str) -> dict:
    """
    Read-through for a single ticker's basic price data.

    Flow:
      fresh cache hit  → return immediately (no network call)
      stale cache hit  → return stale data + kick off background refresh
      cache miss       → synchronous yfinance fetch, then return
      fetch failure    → return sanitized zero-value fallback

    Result is always a safe dict — never None, never has None values.
    """
    ticker = ticker.upper()
    cached = price_cache.get(ticker)

    if cached and not price_cache.price_is_stale(ticker):
        return sanitize_stock_data(cached)

    if cached:
        # Stale-while-revalidate: serve the stale data immediately,
        # refresh in the background so the *next* request gets fresh data.
        threading.Thread(
            target=refresh_prices,
            args=([ticker],),
            daemon=True,
        ).start()
        return sanitize_stock_data(cached)

    # Cache miss — fetch synchronously so this request doesn't return empty
    if not price_cache.is_in_progress(ticker):
        refresh_prices([ticker])

    return sanitize_stock_data(price_cache.get(ticker))


def get_full_quote(ticker: str) -> dict:
    """
    Read-through for the full stock detail page data.

    Requires a full-quote fetch (not just price) because the detail page
    needs pe_ratio, market_cap, 52-week range, etc.

    Flow:
      fresh full quote  → return immediately
      stale full quote  → return stale + background refresh
      no full quote yet → synchronous fetch (first time visiting this stock)
      fetch failure     → sanitized zero-value fallback
    """
    ticker = ticker.upper()
    cached = price_cache.get(ticker)

    if cached and price_cache.has_full_quote(ticker) and not price_cache.quote_is_stale(ticker):
        return sanitize_stock_data(cached, full_quote=True)

    if cached and price_cache.has_full_quote(ticker):
        # Stale full quote — serve it and refresh in background
        threading.Thread(
            target=refresh_quote,
            args=(ticker,),
            daemon=True,
        ).start()
        return sanitize_stock_data(cached, full_quote=True)

    # No full quote in cache yet — must fetch synchronously
    if not price_cache.is_in_progress(ticker):
        refresh_quote(ticker)

    cached = price_cache.get(ticker)
    return sanitize_stock_data(cached, full_quote=True)


def get_batch_prices(tickers: list[str]) -> dict[str, dict]:
    """
    Read-through for multiple tickers (portfolio / watchlist).

    Returns {ticker: sanitized_data}.
    Missing tickers are fetched synchronously; stale ones are background-refreshed.
    The caller always gets a complete map — every input ticker has an entry.
    """
    if not tickers:
        return {}

    result: dict[str, dict] = {}
    missing: list[str] = []
    stale: list[str] = []

    for raw in tickers:
        ticker = raw.upper()
        cached = price_cache.get(ticker)
        if cached and not price_cache.price_is_stale(ticker):
            result[ticker] = sanitize_stock_data(cached)
        elif cached:
            result[ticker] = sanitize_stock_data(cached)   # Serve stale immediately
            stale.append(ticker)
        else:
            missing.append(ticker)

    # Background refresh for stale tickers (non-blocking, best-effort)
    if stale:
        threading.Thread(
            target=refresh_prices,
            args=(stale,),
            daemon=True,
        ).start()

    # Synchronous fetch for missing tickers — these have no cached value at all
    if missing:
        refresh_prices(missing)
        for ticker in missing:
            result[ticker] = sanitize_stock_data(price_cache.get(ticker))

    return result
