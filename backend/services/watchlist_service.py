"""
services/watchlist_service.py — Watchlist management with live price enrichment.
"""
from __future__ import annotations
import oracledb
import yfinance as yf

from db.connection import DBCursor


class WatchlistService:

    def get_watchlist(self, user_id: int):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT s.ticker, s.company_name, s.sector, s.exchange,
                              w.watchlist_id, w.added_at
                         FROM watchlist w
                         JOIN stocks s ON s.stock_id = w.stock_id
                        WHERE w.user_id = :1
                        ORDER BY w.added_at DESC""",
                    [user_id]
                )
                rows = cur.fetchall()

            if not rows:
                return {"watchlist": []}, 200

            # Enrich with live prices
            items = [{
                "watchlist_id":  r[4],
                "ticker":        r[0],
                "company_name":  r[1],
                "sector":        r[2] or "",
                "exchange":      r[3] or "",
                "added_at":      r[5].isoformat() if r[5] else None,
                "price":         None,
                "change_pct":    None,
            } for r in rows]

            tickers = [i["ticker"] for i in items]
            prices  = self._batch_prices(tickers)

            for item in items:
                data = prices.get(item["ticker"], {})
                item["price"]      = data.get("price")
                item["change_pct"] = data.get("change_pct")

            return {"watchlist": items}, 200

        except Exception as e:
            return {"error": str(e)}, 500

    def add(self, user_id: int, ticker: str):
        try:
            # Resolve stock_id — upsert into stocks catalogue if needed
            with DBCursor(auto_commit=True) as cur:
                # Try to find stock in DB
                cur.execute(
                    "SELECT stock_id FROM stocks WHERE ticker = :1",
                    [ticker]
                )
                row = cur.fetchone()

                if row:
                    stock_id = row[0]
                else:
                    # Fetch info from yfinance and insert
                    try:
                        info = yf.Ticker(ticker).info
                        if not info or not info.get("symbol"):
                            return {"error": f"Ticker '{ticker}' not found"}, 404
                        company_name = info.get("longName") or info.get("shortName") or ticker
                        sector   = info.get("sector", "")
                        exchange = info.get("exchange", "")
                    except Exception:
                        company_name = ticker
                        sector = exchange = ""

                    cur.execute(
                        """INSERT INTO stocks (ticker, company_name, sector, exchange)
                           VALUES (:1, :2, :3, :4)
                           RETURNING stock_id INTO :5""",
                        [ticker, company_name, sector, exchange,
                         cur.var(oracledb.NUMBER)]
                    )
                    stock_id = cur.bindvars[-1].getvalue()

                # Insert into watchlist
                cur.execute(
                    """INSERT INTO watchlist (user_id, stock_id)
                       VALUES (:1, :2)""",
                    [user_id, stock_id]
                )

            return {"message": f"{ticker} added to watchlist"}, 201

        except oracledb.IntegrityError:
            return {"error": f"{ticker} is already in your watchlist"}, 409
        except Exception as e:
            return {"error": str(e)}, 500

    def remove(self, user_id: int, ticker: str):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """DELETE FROM watchlist
                        WHERE user_id = :1
                          AND stock_id = (
                              SELECT stock_id FROM stocks WHERE ticker = :2
                          )""",
                    [user_id, ticker]
                )
                deleted = cur.rowcount

            if deleted == 0:
                return {"error": f"{ticker} not found in watchlist"}, 404
            return {"message": f"{ticker} removed from watchlist"}, 200

        except Exception as e:
            return {"error": str(e)}, 500

    # ── helpers ──────────────────────────────────────────────────────────────
    def _batch_prices(self, tickers: list[str]) -> dict[str, dict]:
        """Returns {ticker: {price, change_pct}} for each ticker."""
        result = {}
        if not tickers:
            return result
        try:
            import pandas as pd
            data = yf.download(
                " ".join(tickers), period="2d", interval="1d",
                group_by="ticker", auto_adjust=True, progress=False
            )
            if isinstance(data.columns, pd.MultiIndex):
                for t in tickers:
                    try:
                        closes = data[t]["Close"].dropna()
                        if len(closes) >= 2:
                            result[t] = {
                                "price":      round(float(closes.iloc[-1]), 4),
                                "change_pct": round(
                                    (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2
                                ),
                            }
                        elif len(closes) == 1:
                            result[t] = {"price": round(float(closes.iloc[-1]), 4), "change_pct": 0.0}
                    except Exception:
                        pass
            else:
                # Single ticker
                closes = data["Close"].dropna()
                if not closes.empty and len(tickers) == 1:
                    t = tickers[0]
                    result[t] = {"price": round(float(closes.iloc[-1]), 4), "change_pct": 0.0}
                    if len(closes) >= 2:
                        result[t]["change_pct"] = round(
                            (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2
                        )
        except Exception:
            pass
        return result
