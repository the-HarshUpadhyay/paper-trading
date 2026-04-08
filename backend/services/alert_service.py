from __future__ import annotations
import logging
import oracledb
from db.connection import DBCursor
from utils import scalar_out

logger = logging.getLogger(__name__)


class AlertService:

    def create(self, user_id: int, ticker: str, condition: str, target_price: float):
        ticker = ticker.upper()
        condition = condition.upper()
        try:
            out_var = None
            with DBCursor(auto_commit=True) as cur:
                out_var = cur.var(oracledb.NUMBER)
                cur.execute(
                    """INSERT INTO price_alerts (user_id, ticker, condition, target_price)
                       VALUES (:1, :2, :3, :4)
                       RETURNING alert_id INTO :5""",
                    [user_id, ticker, condition, target_price, out_var],
                )
            alert_id = scalar_out(out_var)
            with DBCursor() as cur:
                cur.execute(
                    """SELECT alert_id, ticker, condition, target_price, is_active, created_at
                         FROM price_alerts WHERE alert_id = :1""",
                    [alert_id],
                )
                row = cur.fetchone()
            return _alert_row(row), 201
        except Exception as e:
            logger.error("alert.create(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def delete(self, user_id: int, alert_id: int):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM price_alerts WHERE alert_id = :1 AND user_id = :2",
                    [alert_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Alert not found"}, 404
            return {"message": "Alert deleted"}, 200
        except Exception as e:
            logger.error("alert.delete(user=%s, alert=%s): %s", user_id, alert_id, e)
            return {"error": str(e)}, 500

    def list_alerts(self, user_id: int):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT alert_id, ticker, condition, target_price, is_active, created_at
                         FROM price_alerts
                        WHERE user_id = :1
                        ORDER BY created_at DESC""",
                    [user_id],
                )
                rows = cur.fetchall()
            return [_alert_row(r) for r in rows], 200
        except Exception as e:
            logger.error("alert.list(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def list_notifications(self, user_id: int, unread_only: bool = True):
        try:
            with DBCursor() as cur:
                if unread_only:
                    cur.execute(
                        """SELECT notif_id, message, is_read, created_at
                             FROM notifications
                            WHERE user_id = :1 AND is_read = 0
                            ORDER BY created_at DESC""",
                        [user_id],
                    )
                else:
                    cur.execute(
                        """SELECT notif_id, message, is_read, created_at
                             FROM notifications
                            WHERE user_id = :1
                            ORDER BY created_at DESC
                           FETCH FIRST 50 ROWS ONLY""",
                        [user_id],
                    )
                rows = cur.fetchall()
            return [_notif_row(r) for r in rows], 200
        except Exception as e:
            logger.error("alert.list_notifications(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def mark_read(self, user_id: int, notif_ids: list):
        try:
            if not notif_ids:
                return {"message": "ok"}, 200
            placeholders = ", ".join(f":{i+1}" for i in range(len(notif_ids)))
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    f"UPDATE notifications SET is_read = 1 WHERE user_id = :{len(notif_ids)+1} AND notif_id IN ({placeholders})",
                    notif_ids + [user_id],
                )
            return {"message": "Marked as read"}, 200
        except Exception as e:
            logger.error("alert.mark_read(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500


def check_alerts(ticker: str, current_price: float) -> None:
    ticker = ticker.upper()
    try:
        with DBCursor() as cur:
            cur.execute(
                """SELECT a.alert_id, a.user_id, a.condition, a.target_price
                     FROM price_alerts a
                    WHERE a.ticker = :1 AND a.is_active = 1""",
                [ticker],
            )
            rows = cur.fetchall()

        for row in rows:
            alert_id, user_id, condition, target = row
            target = float(target)

            triggered = False
            if condition == "ABOVE" and current_price >= target:
                triggered = True
            elif condition == "BELOW" and current_price <= target:
                triggered = True

            if not triggered:
                continue

            try:
                direction = "above" if condition == "ABOVE" else "below"
                message = (
                    f"{ticker} is {direction} your target of "
                    f"{target:.2f} (current: {current_price:.2f})"
                )
                with DBCursor(auto_commit=True) as cur:
                    cur.execute(
                        """INSERT INTO notifications (user_id, alert_id, message)
                           VALUES (:1, :2, :3)""",
                        [user_id, alert_id, message],
                    )
                    cur.execute(
                        """UPDATE price_alerts
                              SET is_active = 0, triggered_at = SYSTIMESTAMP
                            WHERE alert_id = :1""",
                        [alert_id],
                    )
            except Exception as e:
                logger.warning("check_alerts trigger error (alert=%s): %s", alert_id, e)

    except Exception as e:
        logger.warning("check_alerts(%s): %s", ticker, e)


def _alert_row(row) -> dict:
    return {
        "alert_id":     row[0],
        "ticker":       row[1],
        "condition":    row[2],
        "target_price": float(row[3]),
        "is_active":    bool(row[4]),
        "created_at":   row[5].isoformat() if row[5] else None,
    }


def _notif_row(row) -> dict:
    return {
        "notif_id":   row[0],
        "message":    row[1],
        "is_read":    bool(row[2]),
        "created_at": row[3].isoformat() if row[3] else None,
    }
