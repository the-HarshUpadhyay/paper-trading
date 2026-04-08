"""
services/fx_service.py — Live foreign-exchange rates relative to USD.

Rates are fetched once per calendar day from yfinance using standard Forex
tickers (e.g. USDINR=X gives how many INR = 1 USD).

The in-memory cache is keyed by date so it auto-refreshes at midnight without
any cron job.  Falls back to stale rates if yfinance is unavailable.

Supported currencies: USD, INR, GBP, EUR, JPY, HKD
"""

import logging
import threading
from datetime import date

import yfinance as yf

logger = logging.getLogger(__name__)

# ── Fallback rates (used when yfinance is unreachable) ──────────
_FALLBACK = {
    "USD": 1.0,
    "INR": 84.0,
    "GBP": 0.79,
    "EUR": 0.91,
    "JPY": 149.5,
    "HKD": 7.78,
}

# ── yfinance forex ticker → our currency code ───────────────────
_FOREX_TICKERS = {
    "USDINR=X": "INR",
    "GBPUSD=X": "GBP",   # price = USD per 1 GBP → invert to get GBP per USD
    "EURUSD=X": "EUR",   # price = USD per 1 EUR → invert
    "USDJPY=X": "JPY",
    "USDHKD=X": "HKD",
}

_cache: dict | None = None   # {currency: rate}
_cache_date: date | None = None
_lock = threading.Lock()


def _fetch_rates() -> dict[str, float]:
    """Download today's opening rates from yfinance."""
    rates = {"USD": 1.0}
    try:
        tickers_str = " ".join(_FOREX_TICKERS.keys())
        raw = yf.download(
            tickers_str,
            period="2d",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if raw is None or raw.empty:
            raise ValueError("Empty dataframe from yfinance")

        close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]

        for yf_ticker, currency in _FOREX_TICKERS.items():
            try:
                if hasattr(close, "columns"):
                    # MultiIndex or multi-ticker — get column for this ticker
                    col_keys = [c for c in close.columns if yf_ticker in str(c)]
                    price = float(close[col_keys[0]].dropna().iloc[-1]) if col_keys else None
                else:
                    price = float(close.dropna().iloc[-1])

                if price and price > 0:
                    # GBP and EUR are quoted as USD-per-unit; invert to get units-per-USD
                    if currency in ("GBP", "EUR"):
                        rates[currency] = round(1.0 / price, 6)
                    else:
                        rates[currency] = round(price, 4)
            except Exception as e:
                logger.debug("FX rate for %s failed: %s", yf_ticker, e)
                rates.setdefault(currency, _FALLBACK.get(currency, 1.0))

    except Exception as e:
        logger.warning("FX fetch failed (%s) — using fallback rates", e)
        return dict(_FALLBACK)

    # Fill any missing currencies with fallback
    for currency, fallback in _FALLBACK.items():
        rates.setdefault(currency, fallback)

    logger.info("FX rates refreshed: %s", rates)
    return rates


def get_rates() -> dict[str, float]:
    """
    Return today's exchange rates relative to USD.
    Result format: {"USD": 1.0, "INR": 84.5, "GBP": 0.79, ...}

    Thread-safe, cached per calendar day.  Uses double-checked locking so the
    network fetch happens outside the lock, preventing all threads from blocking
    on a slow yfinance request.
    """
    global _cache, _cache_date

    today = date.today()

    # Fast path — no lock needed for a read when cache is already warm
    with _lock:
        if _cache is not None and _cache_date == today:
            return dict(_cache)

    # Fetch outside the lock so other threads aren't blocked during I/O
    fresh = _fetch_rates()

    # Re-acquire lock to write; re-check in case another thread already updated
    with _lock:
        if _cache_date != today:
            _cache = fresh
            _cache_date = today
        return dict(_cache)
