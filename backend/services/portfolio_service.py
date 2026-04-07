"""
services/portfolio_service.py — Live portfolio valuation and snapshot management.
"""
from __future__ import annotations
import yfinance as yf

from db.connection import DBCursor, get_connection
import oracledb


class PortfolioService:

    def get_portfolio(self, user_id: int):
        """
        Returns:
          - cash_balance
          - holdings  (with live price, P/L)
          - total_value (cash + holdings market value)
          - total_invested (cost basis)
          - total_pl, total_pl_pct
        """
        try:
            # 1. Fetch holdings from DB
            with DBCursor() as cur:
                cur.execute(
                    """SELECT h.stock_id, s.ticker, s.company_name,
                              h.quantity, h.avg_buy_price
                         FROM holdings h
                         JOIN stocks s ON s.stock_id = h.stock_id
                        WHERE h.user_id = :1 AND h.quantity > 0
                        ORDER BY s.ticker""",
                    [user_id]
                )
                rows = cur.fetchall()

                # Cash balance
                cur.execute("SELECT balance FROM users WHERE user_id = :1", [user_id])
                cash_row = cur.fetchone()

            cash_balance = float(cash_row[0]) if cash_row else 0.0

            if not rows:
                return {
                    "cash_balance":    cash_balance,
                    "holdings":        [],
                    "total_value":     cash_balance,
                    "total_invested":  0.0,
                    "holdings_value":  0.0,
                    "total_pl":        0.0,
                    "total_pl_pct":    0.0,
                }, 200

            # 2. Fetch live prices for all holdings (one batch call)
            tickers = [r[1] for r in rows]
            prices  = self._batch_price(tickers)

            holdings_list = []
            total_invested = 0.0
            holdings_value = 0.0

            for stock_id, ticker, company, qty, avg_cost in rows:
                qty       = float(qty)
                avg_cost  = float(avg_cost)
                cur_price = prices.get(ticker)
                cost_basis = qty * avg_cost
                total_invested += cost_basis

                if cur_price is not None:
                    mkt_val  = qty * cur_price
                    pl       = mkt_val - cost_basis
                    pl_pct   = (pl / cost_basis * 100) if cost_basis else 0.0
                    holdings_value += mkt_val
                else:
                    mkt_val = pl = pl_pct = None

                holdings_list.append({
                    "stock_id":      stock_id,
                    "ticker":        ticker,
                    "company_name":  company,
                    "quantity":      qty,
                    "avg_buy_price": avg_cost,
                    "current_price": cur_price,
                    "market_value":  round(mkt_val, 2) if mkt_val is not None else None,
                    "cost_basis":    round(cost_basis, 2),
                    "pl":            round(pl, 2) if pl is not None else None,
                    "pl_pct":        round(pl_pct, 2) if pl_pct is not None else None,
                })

            total_value = cash_balance + holdings_value
            total_pl    = holdings_value - total_invested
            total_pl_pct = (total_pl / total_invested * 100) if total_invested else 0.0

            return {
                "cash_balance":   round(cash_balance, 2),
                "holdings":       holdings_list,
                "total_value":    round(total_value, 2),
                "total_invested": round(total_invested, 2),
                "holdings_value": round(holdings_value, 2),
                "total_pl":       round(total_pl, 2),
                "total_pl_pct":   round(total_pl_pct, 2),
            }, 200

        except Exception as e:
            return {"error": str(e)}, 500

    def get_snapshots(self, user_id: int, days: int = 30):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT snapshot_date, total_value, cash_balance, holdings_value
                         FROM portfolio_snapshots
                        WHERE user_id = :1
                          AND snapshot_date >= SYSTIMESTAMP - INTERVAL ':2' DAY
                        ORDER BY snapshot_date ASC""".replace("':2'", str(days)),
                    [user_id]
                )
                rows = cur.fetchall()

            snapshots = [{
                "date":           r[0].isoformat() if r[0] else None,
                "total_value":    float(r[1]),
                "cash_balance":   float(r[2]),
                "holdings_value": float(r[3]),
            } for r in rows]
            return {"snapshots": snapshots}, 200
        except Exception as e:
            return {"error": str(e)}, 500

    def save_snapshot_after_trade(self, user_id: int):
        """Called after every trade to persist a portfolio snapshot."""
        result, status = self.get_portfolio(user_id)
        if status != 200:
            return
        holdings_value = result.get("holdings_value", 0.0)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.callproc("pkg_portfolio.save_snapshot", [user_id, holdings_value])
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    # ── helpers ────────────────────────────────────────────────────────────
    def _batch_price(self, tickers: list[str]) -> dict[str, float]:
        """Fetch latest closing prices for a list of tickers."""
        if not tickers:
            return {}
        prices = {}
        try:
            data = yf.download(
                " ".join(tickers), period="2d", interval="1d",
                group_by="ticker", auto_adjust=True, progress=False
            )
            import pandas as pd
            if isinstance(data.columns, pd.MultiIndex):
                for t in tickers:
                    try:
                        closes = data[t]["Close"].dropna()
                        if not closes.empty:
                            prices[t] = round(float(closes.iloc[-1]), 4)
                    except Exception:
                        pass
            else:
                # Single ticker
                closes = data["Close"].dropna()
                if not closes.empty and len(tickers) == 1:
                    prices[tickers[0]] = round(float(closes.iloc[-1]), 4)
        except Exception:
            pass
        return prices
