"""
services/portfolio_service.py — Live portfolio valuation and snapshot management.

Architecture change (v2):
  _batch_price() now reads from the in-memory cache via market_data.get_batch_prices()
  instead of calling yfinance directly on every portfolio page load.

  The scheduler keeps prices warm for all held tickers in the background,
  so portfolio requests are served from cache (sub-millisecond) rather than
  blocking on a yfinance network call.

  Graceful degradation: if a price is missing from cache (scheduler not yet
  run, or yfinance unavailable), holdings are returned with price=0 and
  market_value/P&L fields set to 0 — the UI never receives None.
"""
from __future__ import annotations

import logging

import oracledb

from db.connection import DBCursor, get_connection
from services.market_data import get_batch_prices

logger = logging.getLogger(__name__)


class PortfolioService:

    def get_portfolio(self, user_id: int):
        """
        Returns:
          cash_balance, holdings (with live price, P/L),
          total_value, total_invested, total_pl, total_pl_pct.

        All numeric fields are guaranteed to be float (never None).
        """
        try:
            with DBCursor() as cur:
                # 1. Holdings with stock metadata
                cur.execute(
                    """SELECT h.stock_id, s.ticker, s.company_name, s.sector,
                              h.quantity, h.avg_buy_price
                         FROM holdings h
                         JOIN stocks s ON s.stock_id = h.stock_id
                        WHERE h.user_id = :1 AND h.quantity > 0
                        ORDER BY s.ticker""",
                    [user_id],
                )
                rows = cur.fetchall()

                # 2. Cash balance
                cur.execute(
                    "SELECT balance FROM users WHERE user_id = :1",
                    [user_id],
                )
                cash_row = cur.fetchone()

            cash_balance = float(cash_row[0]) if cash_row else 0.0

            if not rows:
                return {
                    "cash_balance":   cash_balance,
                    "holdings":       [],
                    "total_value":    cash_balance,
                    "total_invested": 0.0,
                    "holdings_value": 0.0,
                    "total_pl":       0.0,
                    "total_pl_pct":   0.0,
                }, 200

            # 3. Read prices from cache (never yfinance directly)
            tickers = [r[1] for r in rows]
            prices  = self._batch_price(tickers)

            holdings_list  = []
            total_invested = 0.0
            holdings_value = 0.0

            for stock_id, ticker, company, sector, qty, avg_cost in rows:
                qty        = float(qty)
                avg_cost   = float(avg_cost)
                cost_basis = qty * avg_cost
                total_invested += cost_basis

                # price defaults to 0.0 when not in cache (safe fallback)
                cur_price = prices.get(ticker, {}).get("price", 0.0)

                mkt_val        = qty * cur_price
                pl             = mkt_val - cost_basis
                pl_pct         = (pl / cost_basis * 100) if cost_basis else 0.0
                holdings_value += mkt_val

                holdings_list.append({
                    "stock_id":      stock_id,
                    "ticker":        ticker,
                    "company_name":  company,
                    "sector":        sector or "",
                    "quantity":      qty,
                    "avg_buy_price": round(avg_cost, 4),
                    "current_price": round(cur_price, 4),
                    "market_value":  round(mkt_val, 2),
                    "cost_basis":    round(cost_basis, 2),
                    "pl":            round(pl, 2),
                    "pl_pct":        round(pl_pct, 2),
                })

            total_value  = cash_balance + holdings_value
            total_pl     = holdings_value - total_invested
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
            logger.error("get_portfolio(user=%s) failed: %s", user_id, e)
            return {"error": str(e)}, 500

    def get_snapshots(self, user_id: int, days: int = 30):
        """Return portfolio value snapshots for the last *days* days."""
        # Clamp days to a safe integer range to prevent injection
        days = max(1, min(int(days), 3650))
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT snapshot_date, total_value, cash_balance, holdings_value
                         FROM portfolio_snapshots
                        WHERE user_id = :1
                          AND snapshot_date >= SYSTIMESTAMP - NUMTODSINTERVAL(:2, 'DAY')
                        ORDER BY snapshot_date ASC""",
                    [user_id, days],
                )
                rows = cur.fetchall()

            snapshots = [
                {
                    "date":           r[0].isoformat() if r[0] else None,
                    "total_value":    float(r[1]),
                    "cash_balance":   float(r[2]),
                    "holdings_value": float(r[3]),
                }
                for r in (rows or [])
            ]
            return {"snapshots": snapshots}, 200

        except Exception as e:
            logger.error("get_snapshots(user=%s) failed: %s", user_id, e)
            return {"error": str(e)}, 500

    def save_snapshot_after_trade(
        self, user_id: int, ticker: str = None, fill_price: float = None
    ) -> None:
        """Called after every trade to persist a portfolio snapshot.

        Pass *ticker* and *fill_price* to seed the price cache with the known
        trade price so the snapshot reflects the correct holdings value even
        before the background scheduler has had a chance to refresh prices.
        """
        if ticker and fill_price:
            from services.cache import price_cache
            existing = price_cache.get(ticker) or {}
            if not existing.get("price"):
                price_cache.set_price(ticker.upper(), {"price": fill_price, "change_pct": 0.0})
        result, status = self.get_portfolio(user_id)
        if status != 200:
            return
        holdings_value = result.get("holdings_value", 0.0)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.callproc("pkg_portfolio.save_snapshot", [user_id, holdings_value])
            conn.commit()
        except Exception as e:
            logger.warning("save_snapshot_after_trade(user=%s) failed: %s", user_id, e)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _batch_price(self, tickers: list[str]) -> dict[str, dict]:
        """
        Return {ticker: {price, change_pct, ...}} for each ticker.

        Delegates entirely to get_batch_prices() (cache read-through).
        No yfinance call here — the scheduler keeps prices warm.
        """
        return get_batch_prices(tickers)
