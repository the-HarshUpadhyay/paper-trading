"""
services/stock_service.py — Stock search, quote, and OHLCV history.

Architecture change (v2):
  All price data is now read from the in-memory cache (services/cache.py).
  yfinance is only called via market_data helpers, never directly here.

  search()     — DB catalogue first, prices from cache; yfinance only for
                 unknown tickers not yet catalogued in the DB.
  get_quote()  — full quote from cache (via market_data.get_full_quote),
                 returns sanitized dict; never returns None fields.
  get_history()— OHLCV history still fetched from yfinance directly because
                 it is a large time-series query unsuitable for the price cache.
  _upsert_stock() — unchanged, best-effort DB sync after any yfinance fetch.
"""
from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from db.connection import DBCursor
from services.market_data import (
    get_full_quote,
    get_batch_prices,
    refresh_quote,
    sanitize_stock_data,
)

logger = logging.getLogger(__name__)


class StockService:

    # ── Search ─────────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict]:
        """
        Search for stocks matching *query*.

        Steps:
          1. Prefix/fuzzy match against the stocks catalogue in the DB.
          2. Enrich each result with a live price from the cache
             (non-blocking; falls back to 0.0 if no cache entry yet).
          3. If the DB returned nothing and query looks like a raw ticker,
             try yfinance directly as a last resort and upsert into DB.

        Always returns a list (never None).  All price fields are sanitized.
        """
        query = (query or "").strip()
        if not query:
            return []

        results: list[dict] = []

        # ── Step 1: DB catalogue lookup ────────────────────────────────────
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT ticker, company_name, sector, exchange
                         FROM stocks
                        WHERE UPPER(ticker)       LIKE UPPER(:1) || '%'
                           OR UPPER(company_name) LIKE '%' || UPPER(:2) || '%'
                        ORDER BY ticker
                        FETCH FIRST 10 ROWS ONLY""",
                    [query, query],
                )
                rows = cur.fetchall()

            for ticker, name, sector, exchange in (rows or []):
                results.append({
                    "ticker":       ticker or "",
                    "company_name": name   or "",
                    "sector":       sector or "",
                    "exchange":     exchange or "",
                    "price":        0.0,
                    "change_pct":   0.0,
                })
        except Exception as e:
            logger.warning("search DB lookup failed: %s", e)

        # ── Step 2: Enrich with cached prices (no yfinance call here) ──────
        if results:
            tickers = [r["ticker"] for r in results if r["ticker"]]
            prices  = get_batch_prices(tickers)          # read-through cache
            for r in results:
                data = prices.get(r["ticker"], {})
                r["price"]      = data.get("price",      0.0)
                r["change_pct"] = data.get("change_pct", 0.0)

        # ── Step 3: Unknown ticker — yfinance fallback ─────────────────────
        # Only reached when the DB has no matching rows (e.g., first-time search).
        if not results and len(query) <= 15:
            base = query.upper().rstrip(".")
            for try_ticker in [base, f"{base}.NS", f"{base}.BO"]:
                try:
                    info = yf.Ticker(try_ticker).info
                    # Guard against None or empty info dicts
                    if not info or not isinstance(info, dict) or not info.get("symbol"):
                        continue

                    symbol = str(info["symbol"])
                    price  = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                    results.append({
                        "ticker":       symbol,
                        "company_name": str(info.get("longName") or info.get("shortName") or symbol),
                        "sector":       str(info.get("sector")   or ""),
                        "exchange":     str(info.get("exchange") or ""),
                        "price":        float(price) if price else 0.0,
                        "change_pct":   0.0,
                    })
                    # Persist to DB catalogue so next search is instant
                    self._upsert_stock(
                        results[-1]["ticker"],
                        results[-1]["company_name"],
                        results[-1]["sector"],
                        results[-1]["exchange"],
                    )
                    break
                except Exception as e:
                    logger.debug("yfinance fallback for %s failed: %s", try_ticker, e)

        return results

    # ── Live Quote ──────────────────────────────────────────────────────────

    def get_quote(self, ticker: str) -> tuple[dict, int]:
        """
        Return a full stock quote for *ticker*.

        Reads from cache first (via market_data.get_full_quote).
        If the ticker does not exist in yfinance, returns 404.
        All None fields are replaced with safe defaults before returning.
        """
        ticker = ticker.upper().strip()

        # get_full_quote() handles: cache hit → return, stale → background
        # refresh, miss → synchronous fetch.  Returns sanitized dict always.
        data = get_full_quote(ticker)

        # A zero price AND no company name means the ticker was never found
        if data.get("price") == 0.0 and data.get("company_name") in ("N/A", ""):
            return {"error": f"Ticker '{ticker}' not found"}, 404

        # Ensure ticker field is correct
        data["ticker"] = ticker

        # Upsert into DB catalogue (best-effort, non-blocking)
        self._upsert_stock(
            ticker,
            data.get("company_name", ticker),
            data.get("sector",   ""),
            data.get("exchange", ""),
        )

        return data, 200

    # ── Historical OHLCV ────────────────────────────────────────────────────

    def get_history(self, ticker: str, period: str, interval: str) -> tuple[dict, int]:
        """
        Return OHLCV history for *ticker*.

        Historical data is large time-series that cannot be cached in the
        price cache (different shape / size per request).  yfinance is called
        directly here; this is the only intentional direct yfinance call in
        the service layer.
        """
        valid_periods   = {"1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"}
        valid_intervals = {"1m","2m","5m","15m","30m","60m","90m","1h","1d","5d","1wk","1mo","3mo"}
        if period   not in valid_periods:   period   = "1mo"
        if interval not in valid_intervals: interval = "1d"

        try:
            df: pd.DataFrame = yf.download(
                ticker, period=period, interval=interval,
                auto_adjust=True, progress=False,
            )
            if df is None or df.empty:
                return {"error": f"No history data for '{ticker}'"}, 404

            df = df.dropna()
            # Remove timezone info so timestamps serialise cleanly to ISO-8601
            if hasattr(df.index, "tz_localize"):
                df.index = df.index.tz_localize(None)

            # Flatten MultiIndex columns if yfinance returns them
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            records = []
            for ts, row in df.iterrows():
                records.append({
                    "time":   ts.isoformat(),
                    "open":   round(float(row.get("Open",  0) or 0), 4),
                    "high":   round(float(row.get("High",  0) or 0), 4),
                    "low":    round(float(row.get("Low",   0) or 0), 4),
                    "close":  round(float(row.get("Close", 0) or 0), 4),
                    "volume": int(row["Volume"]) if "Volume" in row and row["Volume"] else 0,
                })

            return {"ticker": ticker, "period": period, "interval": interval, "data": records}, 200

        except Exception as e:
            logger.error("get_history(%s) failed: %s", ticker, e)
            return {"error": str(e)}, 500

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _upsert_stock(self, ticker: str, company_name: str, sector: str, exchange: str) -> None:
        """
        Keep the stocks catalogue in sync.  Best-effort: never crashes the caller.
        """
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """MERGE INTO stocks dst
                       USING (SELECT :1 AS ticker FROM dual) src
                          ON (dst.ticker = src.ticker)
                     WHEN NOT MATCHED THEN
                       INSERT (ticker, company_name, sector, exchange)
                       VALUES (:2, :3, :4, :5)
                     WHEN MATCHED THEN
                       UPDATE SET company_name = :6,
                                  sector       = :7,
                                  exchange     = :8""",
                    [
                        ticker,
                        ticker, company_name, sector or "", exchange or "",
                        company_name, sector or "", exchange or "",
                    ],
                )
        except Exception as e:
            logger.debug("_upsert_stock(%s) failed (non-critical): %s", ticker, e)
