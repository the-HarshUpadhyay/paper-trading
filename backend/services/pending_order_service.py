from __future__ import annotations
import logging
import oracledb
from db.connection import DBCursor, get_connection
from utils import scalar_out

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    return {
        "order_id":    row[0],
        "ticker":      row[1],
        "company_name":row[2],
        "order_side":  row[3],
        "order_type":  row[4],
        "quantity":    float(row[5]),
        "limit_price": float(row[6]) if row[6] is not None else None,
        "stop_price":  float(row[7]) if row[7] is not None else None,
        "status":      row[8],
        "created_at":  row[9].isoformat() if row[9] else None,
        "expires_at":  row[10].isoformat() if row[10] else None,
        "filled_at":   row[11].isoformat() if row[11] else None,
        "filled_price":float(row[12]) if row[12] is not None else None,
    }


class PendingOrderService:

    def place(self, user_id: int, ticker: str, side: str, order_type: str,
              quantity: float, limit_price=None, stop_price=None, expires_at=None):
        ticker = ticker.upper()
        try:
            with DBCursor() as cur:
                cur.execute(
                    "SELECT stock_id FROM stocks WHERE ticker = :1", [ticker]
                )
                row = cur.fetchone()
                if not row:
                    return {"error": f"Ticker '{ticker}' not found"}, 404
                stock_id = row[0]

            out_var = None
            with DBCursor(auto_commit=True) as cur:
                out_var = cur.var(oracledb.NUMBER)
                cur.execute(
                    """INSERT INTO pending_orders
                           (user_id, stock_id, order_side, order_type, quantity,
                            limit_price, stop_price, expires_at)
                       VALUES (:1, :2, :3, :4, :5, :6, :7, :8)
                       RETURNING order_id INTO :9""",
                    [user_id, stock_id, side.upper(), order_type.upper(),
                     quantity, limit_price, stop_price, expires_at, out_var],
                )
            order_id = scalar_out(out_var)
            return self._get_by_id(order_id)
        except Exception as e:
            logger.error("pending_order.place(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def cancel(self, user_id: int, order_id: int):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """UPDATE pending_orders SET status = 'CANCELLED'
                        WHERE order_id = :1 AND user_id = :2 AND status = 'OPEN'""",
                    [order_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Order not found or not cancellable"}, 404
            return {"message": "Order cancelled"}, 200
        except Exception as e:
            logger.error("pending_order.cancel(user=%s, order=%s): %s", user_id, order_id, e)
            return {"error": str(e)}, 500

    def list_orders(self, user_id: int, status: str = "OPEN"):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT p.order_id, s.ticker, s.company_name,
                              p.order_side, p.order_type, p.quantity,
                              p.limit_price, p.stop_price, p.status,
                              p.created_at, p.expires_at, p.filled_at, p.filled_price
                         FROM pending_orders p
                         JOIN stocks s ON s.stock_id = p.stock_id
                        WHERE p.user_id = :1 AND p.status = :2
                        ORDER BY p.created_at DESC""",
                    [user_id, status.upper()],
                )
                rows = cur.fetchall()
            return [_row_to_dict(r) for r in rows], 200
        except Exception as e:
            logger.error("pending_order.list(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def _get_by_id(self, order_id: int):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT p.order_id, s.ticker, s.company_name,
                              p.order_side, p.order_type, p.quantity,
                              p.limit_price, p.stop_price, p.status,
                              p.created_at, p.expires_at, p.filled_at, p.filled_price
                         FROM pending_orders p
                         JOIN stocks s ON s.stock_id = p.stock_id
                        WHERE p.order_id = :1""",
                    [order_id],
                )
                row = cur.fetchone()
            if not row:
                return {"error": "Order not found"}, 404
            return _row_to_dict(row), 201
        except Exception as e:
            logger.error("pending_order._get_by_id(%s): %s", order_id, e)
            return {"error": str(e)}, 500


def check_and_fill(ticker: str, current_price: float) -> None:
    ticker = ticker.upper()
    try:
        with DBCursor() as cur:
            cur.execute(
                """SELECT p.order_id, p.user_id, p.order_side, p.order_type,
                          p.quantity, p.limit_price, p.stop_price
                     FROM pending_orders p
                     JOIN stocks s ON s.stock_id = p.stock_id
                    WHERE s.ticker = :1 AND p.status = 'OPEN'""",
                [ticker],
            )
            rows = cur.fetchall()

        if not rows:
            return

        from services.trading_service import TradingService
        svc = TradingService()

        for row in rows:
            order_id, user_id, side, otype, qty, limit_p, stop_p = row
            qty      = float(qty)
            limit_p  = float(limit_p) if limit_p is not None else None
            stop_p   = float(stop_p)  if stop_p  is not None else None

            triggered = False
            fill_price = current_price

            if otype == "LIMIT":
                if side == "BUY"  and current_price <= limit_p:
                    triggered  = True
                    fill_price = limit_p
                elif side == "SELL" and current_price >= limit_p:
                    triggered  = True
                    fill_price = limit_p
            elif otype == "STOP":
                if side == "SELL" and current_price <= stop_p:
                    triggered = True
            elif otype == "STOP_LIMIT":
                if stop_p and limit_p:
                    if side == "SELL" and current_price <= stop_p:
                        triggered  = True
                        fill_price = limit_p
                    elif side == "BUY" and current_price >= stop_p:
                        triggered  = True
                        fill_price = limit_p

            if not triggered:
                continue

            try:
                if side == "BUY":
                    result, status = svc.buy(user_id, ticker, qty, fill_price)
                else:
                    result, status = svc.sell(user_id, ticker, qty, fill_price)

                if status in (200, 201):
                    with DBCursor(auto_commit=True) as cur:
                        cur.execute(
                            """UPDATE pending_orders
                                  SET status = 'FILLED',
                                      filled_at = SYSTIMESTAMP,
                                      filled_price = :1
                                WHERE order_id = :2""",
                            [fill_price, order_id],
                        )
                else:
                    logger.warning(
                        "check_and_fill: trade failed for order %s: %s", order_id, result
                    )
            except Exception as e:
                logger.warning("check_and_fill order %s fill error: %s", order_id, e)

    except Exception as e:
        logger.warning("check_and_fill(%s): %s", ticker, e)


def check_and_fill_all(tickers: list[str], prices: dict) -> None:
    for ticker in tickers:
        data = prices.get(ticker)
        if data and data.get("price"):
            try:
                check_and_fill(ticker, data["price"])
            except Exception as e:
                logger.warning("check_and_fill_all(%s): %s", ticker, e)
