"""
services/watchlist_service.py — Watchlist management with live price enrichment.

Architecture change (v2):
  _batch_prices() now reads from the in-memory cache via market_data.get_batch_prices()
  instead of calling yfinance on every watchlist request.

  All price fields are sanitized — None values are replaced with 0.0 before
  the response is built, so the frontend always receives well-typed data.
"""
from __future__ import annotations

import logging

import oracledb
import yfinance as yf

from db.connection import DBCursor
from services.market_data import get_batch_prices

logger = logging.getLogger(__name__)


class WatchlistService:

    def get_watchlist(self, user_id: int):
        """
        Return the user's watchlist enriched with latest prices.
        Prices come from the shared in-memory cache; no yfinance call here.
        """
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT s.ticker, s.company_name, s.sector, s.exchange,
                              w.watchlist_id, w.added_at
                         FROM watchlist w
                         JOIN stocks s ON s.stock_id = w.stock_id
                        WHERE w.user_id = :1
                        ORDER BY w.added_at DESC""",
                    [user_id],
                )
                rows = cur.fetchall()

            if not rows:
                return {"watchlist": []}, 200

            items = [
                {
                    "watchlist_id": r[4],
                    "ticker":       r[0] or "",
                    "company_name": r[1] or "",
                    "sector":       r[2] or "",
                    "exchange":     r[3] or "",
                    "added_at":     r[5].isoformat() if r[5] else None,
                    "price":        0.0,
                    "change_pct":   0.0,
                }
                for r in rows
            ]

            # Enrich with cached prices (non-blocking read)
            tickers = [i["ticker"] for i in items if i["ticker"]]
            prices  = self._batch_prices(tickers)

            for item in items:
                data = prices.get(item["ticker"], {})
                item["price"]      = data.get("price",      0.0)
                item["change_pct"] = data.get("change_pct", 0.0)

            return {"watchlist": items}, 200

        except Exception as e:
            logger.error("get_watchlist(user=%s) failed: %s", user_id, e)
            return {"error": str(e)}, 500

    def add(self, user_id: int, ticker: str):
        """
        Add *ticker* to the user's watchlist.

        If the stock is not yet in the DB catalogue, fetch its name/sector
        from yfinance and insert it.  yfinance is only called here because
        we need the company name for a brand-new ticker — this is the one
        acceptable direct call outside of the scheduler.
        """
        ticker = ticker.upper().strip()
        try:
            with DBCursor(auto_commit=True) as cur:
                # Resolve existing stock_id
                cur.execute(
                    "SELECT stock_id FROM stocks WHERE ticker = :1",
                    [ticker],
                )
                row = cur.fetchone()

                if row:
                    stock_id = row[0]
                else:
                    # New ticker — fetch metadata from yfinance
                    company_name = ticker
                    sector = exchange = ""
                    try:
                        info = yf.Ticker(ticker).info
                        if info and isinstance(info, dict) and info.get("symbol"):
                            company_name = str(
                                info.get("longName") or info.get("shortName") or ticker
                            )
                            sector   = str(info.get("sector",   "") or "")
                            exchange = str(info.get("exchange", "") or "")
                        elif info is None or not info.get("symbol"):
                            return {"error": f"Ticker '{ticker}' not found"}, 404
                    except Exception as e:
                        logger.warning("yfinance info failed for %s: %s", ticker, e)
                        # Proceed with ticker as company_name (graceful degradation)

                    out_var = cur.var(oracledb.NUMBER)
                    cur.execute(
                        """INSERT INTO stocks (ticker, company_name, sector, exchange)
                           VALUES (:1, :2, :3, :4)
                           RETURNING stock_id INTO :5""",
                        [ticker, company_name, sector, exchange, out_var],
                    )
                    stock_id = out_var.getvalue()

                # Insert into watchlist
                cur.execute(
                    "INSERT INTO watchlist (user_id, stock_id) VALUES (:1, :2)",
                    [user_id, stock_id],
                )

            return {"message": f"{ticker} added to watchlist"}, 201

        except oracledb.IntegrityError:
            return {"error": f"{ticker} is already in your watchlist"}, 409
        except Exception as e:
            logger.error("watchlist.add(user=%s, ticker=%s) failed: %s", user_id, ticker, e)
            return {"error": str(e)}, 500

    def remove(self, user_id: int, ticker: str):
        """Remove *ticker* from the user's watchlist."""
        ticker = ticker.upper().strip()
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """DELETE FROM watchlist
                        WHERE user_id  = :1
                          AND stock_id = (
                              SELECT stock_id FROM stocks WHERE ticker = :2
                          )""",
                    [user_id, ticker],
                )
                deleted = cur.rowcount

            if deleted == 0:
                return {"error": f"{ticker} not found in watchlist"}, 404
            return {"message": f"{ticker} removed from watchlist"}, 200

        except Exception as e:
            logger.error("watchlist.remove(user=%s, ticker=%s) failed: %s", user_id, ticker, e)
            return {"error": str(e)}, 500

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _batch_prices(self, tickers: list[str]) -> dict[str, dict]:
        """
        Return {ticker: {price, change_pct}} for each ticker.
        Delegates to the shared cache read-through in market_data.
        """
        return get_batch_prices(tickers)
