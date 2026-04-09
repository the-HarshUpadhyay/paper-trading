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
from utils import scalar_out

logger = logging.getLogger(__name__)


class WatchlistService:

    def get_watchlist(self, user_id: int):
        """
        Return the user's watchlist enriched with latest prices, plus ALL
        folders for this user (including empty ones).
        Prices come from the shared in-memory cache; no yfinance call here.
        """
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT s.ticker, s.company_name, s.sector, s.exchange,
                              w.watchlist_id, w.added_at,
                              w.folder_id,
                              NVL(f.name, 'Uncategorised') AS folder_name
                         FROM watchlist w
                         JOIN stocks s ON s.stock_id = w.stock_id
                         LEFT JOIN watchlist_folders f ON f.folder_id = w.folder_id
                        WHERE w.user_id = :1
                        ORDER BY w.added_at DESC""",
                    [user_id],
                )
                rows = cur.fetchall()

                # Fetch ALL folders for this user so empty folders are visible
                cur.execute(
                    """SELECT folder_id, name FROM watchlist_folders
                        WHERE user_id = :1 ORDER BY created_at""",
                    [user_id],
                )
                folder_rows = cur.fetchall()

            folders = [{"folder_id": r[0], "name": r[1]} for r in folder_rows]

            if not rows:
                return {"watchlist": [], "folders": folders}, 200

            items = [
                {
                    "watchlist_id": r[4],
                    "ticker":       r[0] or "",
                    "company_name": r[1] or "",
                    "sector":       r[2] or "",
                    "exchange":     r[3] or "",
                    "added_at":     r[5].isoformat() if r[5] else None,
                    "folder_id":    r[6],
                    "folder_name":  r[7] or "Uncategorised",
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

            return {"watchlist": items, "folders": folders}, 200

        except Exception as e:
            logger.error("get_watchlist(user=%s) failed: %s", user_id, e)
            return {"error": str(e)}, 500

    def add(self, user_id: int, ticker: str, folder_id: int | None = None):
        """
        Add *ticker* to the user's watchlist, optionally into a specific folder.

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
                    stock_id = scalar_out(out_var)

                # Insert into watchlist with optional folder assignment
                cur.execute(
                    "INSERT INTO watchlist (user_id, stock_id, folder_id) VALUES (:1, :2, :3)",
                    [user_id, stock_id, folder_id],
                )

            return {"message": f"{ticker} added to watchlist"}, 201

        except oracledb.IntegrityError:
            return {"error": f"{ticker} is already in this list"}, 409
        except Exception as e:
            logger.error("watchlist.add(user=%s, ticker=%s) failed: %s", user_id, ticker, e)
            return {"error": str(e)}, 500

    def remove_by_id(self, user_id: int, watchlist_id: int):
        """Remove a specific watchlist entry by its ID (single-list removal)."""
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM watchlist WHERE watchlist_id = :1 AND user_id = :2",
                    [watchlist_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Item not found"}, 404
            return {"message": "Removed"}, 200
        except Exception as e:
            logger.error("watchlist.remove_by_id(user=%s, id=%s) failed: %s", user_id, watchlist_id, e)
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

    def create_folder(self, user_id: int, name: str):
        try:
            with DBCursor(auto_commit=True) as cur:
                out_var = cur.var(oracledb.NUMBER)
                cur.execute(
                    """INSERT INTO watchlist_folders (user_id, name)
                       VALUES (:1, :2)
                       RETURNING folder_id INTO :3""",
                    [user_id, name.strip(), out_var],
                )
            folder_id = scalar_out(out_var)
            return {"folder_id": folder_id, "name": name.strip()}, 201
        except oracledb.IntegrityError:
            return {"error": f"Folder '{name}' already exists"}, 409
        except Exception as e:
            logger.error("watchlist.create_folder(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def rename_folder(self, user_id: int, folder_id: int, name: str):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """UPDATE watchlist_folders SET name = :1
                        WHERE folder_id = :2 AND user_id = :3""",
                    [name.strip(), folder_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Folder not found"}, 404
            return {"folder_id": folder_id, "name": name.strip()}, 200
        except Exception as e:
            logger.error("watchlist.rename_folder(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def delete_folder(self, user_id: int, folder_id: int):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM watchlist_folders WHERE folder_id = :1 AND user_id = :2",
                    [folder_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Folder not found"}, 404
            return {"message": "Folder deleted"}, 200
        except Exception as e:
            logger.error("watchlist.delete_folder(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def move_item(self, user_id: int, watchlist_id: int, folder_id):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """UPDATE watchlist SET folder_id = :1
                        WHERE watchlist_id = :2 AND user_id = :3""",
                    [folder_id, watchlist_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Watchlist item not found"}, 404
            return {"message": "Item moved"}, 200
        except Exception as e:
            logger.error("watchlist.move_item(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _batch_prices(self, tickers: list[str]) -> dict[str, dict]:
        """
        Return {ticker: {price, change_pct}} for each ticker.
        Delegates to the shared cache read-through in market_data.
        """
        return get_batch_prices(tickers)
