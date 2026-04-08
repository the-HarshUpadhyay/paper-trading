"""
services/trading_service.py — Buy / Sell execution via PL/SQL package.
"""
from __future__ import annotations
import oracledb

from db.connection import get_connection
from services.portfolio_service import PortfolioService
from utils import scalar_out


class TradingService:

    def buy(self, user_id: int, ticker: str, quantity: float, price: float):
        conn = get_connection()
        try:
            cur = conn.cursor()
            # Call PL/SQL package procedure
            trans_id_var = cur.var(oracledb.NUMBER)
            cur.callproc(
                "pkg_trading.execute_buy",
                [user_id, ticker, quantity, price, trans_id_var]
            )
            trans_id = scalar_out(trans_id_var)
            conn.commit()

            # Async snapshot save (best-effort)
            try:
                PortfolioService().save_snapshot_after_trade(user_id)
            except Exception:
                pass

            return {
                "message":        "Buy order executed",
                "transaction_id": trans_id,
                "ticker":         ticker,
                "quantity":       quantity,
                "price":          price,
                "total":          round(quantity * price, 2),
            }, 201
        except oracledb.DatabaseError as e:
            conn.rollback()
            error_obj = e.args[0]
            code = getattr(error_obj, "code", 0)
            msg  = getattr(error_obj, "message", str(e))
            # Map Oracle custom error codes (defined in triggers)
            if code == 20001:
                return {"error": "Insufficient holdings"}, 400
            if code == 20002:
                return {"error": msg.split("ORA-20002:")[1].strip() if "ORA-20002:" in msg else "Insufficient balance"}, 400
            return {"error": msg}, 400
        except Exception as e:
            conn.rollback()
            return {"error": str(e)}, 500
        finally:
            conn.close()

    def sell(self, user_id: int, ticker: str, quantity: float, price: float):
        conn = get_connection()
        try:
            cur = conn.cursor()
            trans_id_var = cur.var(oracledb.NUMBER)
            cur.callproc(
                "pkg_trading.execute_sell",
                [user_id, ticker, quantity, price, trans_id_var]
            )
            trans_id = scalar_out(trans_id_var)
            conn.commit()

            try:
                PortfolioService().save_snapshot_after_trade(user_id)
            except Exception:
                pass

            return {
                "message":        "Sell order executed",
                "transaction_id": trans_id,
                "ticker":         ticker,
                "quantity":       quantity,
                "price":          price,
                "total":          round(quantity * price, 2),
            }, 201
        except oracledb.DatabaseError as e:
            conn.rollback()
            error_obj = e.args[0]
            code = getattr(error_obj, "code", 0)
            msg  = getattr(error_obj, "message", str(e))
            if code == 20001:
                clean = msg.split("ORA-20001:")[1].strip() if "ORA-20001:" in msg else "Insufficient holdings"
                return {"error": clean}, 400
            return {"error": msg}, 400
        except Exception as e:
            conn.rollback()
            return {"error": str(e)}, 500
        finally:
            conn.close()

    def get_orders(self, user_id: int, page: int = 1, per_page: int = 20):
        offset = (page - 1) * per_page
        try:
            from db.connection import DBCursor
            with DBCursor() as cur:
                # Total count
                cur.execute(
                    "SELECT COUNT(*) FROM transactions WHERE user_id = :1",
                    [user_id]
                )
                total = cur.fetchone()[0]

                # Paginated data
                cur.execute(
                    """SELECT t.transaction_id, s.ticker, s.company_name,
                              t.transaction_type, t.quantity, t.price,
                              t.total_amount, t.transaction_time
                         FROM transactions t
                         JOIN stocks s ON s.stock_id = t.stock_id
                        WHERE t.user_id = :1
                        ORDER BY t.transaction_time DESC
                       OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY""",
                    [user_id, offset, per_page]
                )
                rows = cur.fetchall()

            orders = [{
                "transaction_id":   r[0],
                "ticker":           r[1],
                "company_name":     r[2],
                "type":             r[3],
                "quantity":         float(r[4]),
                "price":            float(r[5]),
                "total_amount":     float(r[6]),
                "time":             r[7].isoformat() if r[7] else None,
            } for r in rows]

            return {
                "orders":    orders,
                "total":     total,
                "page":      page,
                "per_page":  per_page,
                "pages":     (total + per_page - 1) // per_page,
            }, 200
        except Exception as e:
            return {"error": str(e)}, 500
