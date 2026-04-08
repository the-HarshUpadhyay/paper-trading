from __future__ import annotations
import logging
import oracledb
from db.connection import DBCursor
from utils import scalar_out

logger = logging.getLogger(__name__)


class NotesService:

    def list(self, user_id: int, ticker: str | None = None):
        try:
            with DBCursor() as cur:
                if ticker:
                    cur.execute(
                        """SELECT note_id, title, ticker, created_at, updated_at
                             FROM notes
                            WHERE user_id = :1 AND ticker = :2
                            ORDER BY updated_at DESC""",
                        [user_id, ticker.upper()],
                    )
                else:
                    cur.execute(
                        """SELECT note_id, title, ticker, created_at, updated_at
                             FROM notes
                            WHERE user_id = :1
                            ORDER BY updated_at DESC""",
                        [user_id],
                    )
                rows = cur.fetchall()
            return [
                {
                    "note_id":    r[0],
                    "title":      r[1],
                    "ticker":     r[2] or "",
                    "created_at": r[3].isoformat() if r[3] else None,
                    "updated_at": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ], 200
        except Exception as e:
            logger.error("notes.list(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def get(self, user_id: int, note_id: int):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT note_id, title, ticker, body, created_at, updated_at
                         FROM notes
                        WHERE note_id = :1 AND user_id = :2""",
                    [note_id, user_id],
                )
                row = cur.fetchone()
            if not row:
                return {"error": "Note not found"}, 404
            body_lob = row[3]
            body = body_lob.read() if body_lob is not None else ""
            return {
                "note_id":    row[0],
                "title":      row[1],
                "ticker":     row[2] or "",
                "body":       body,
                "created_at": row[4].isoformat() if row[4] else None,
                "updated_at": row[5].isoformat() if row[5] else None,
            }, 200
        except Exception as e:
            logger.error("notes.get(user=%s, note=%s): %s", user_id, note_id, e)
            return {"error": str(e)}, 500

    def create(self, user_id: int, title: str, body: str, ticker: str | None = None):
        try:
            out_var = None
            with DBCursor(auto_commit=True) as cur:
                out_var = cur.var(oracledb.NUMBER)
                cur.execute(
                    """INSERT INTO notes (user_id, ticker, title, body)
                       VALUES (:1, :2, :3, :4)
                       RETURNING note_id INTO :5""",
                    [user_id, (ticker.upper() if ticker else None), title, body, out_var],
                )
            note_id = scalar_out(out_var)
            return self.get(user_id, note_id)
        except Exception as e:
            logger.error("notes.create(user=%s): %s", user_id, e)
            return {"error": str(e)}, 500

    def update(self, user_id: int, note_id: int, title: str | None = None, body: str | None = None):
        try:
            sets = ["updated_at = SYSTIMESTAMP"]
            params = []
            if title is not None:
                sets.append("title = :{}".format(len(params) + 1))
                params.append(title)
            if body is not None:
                sets.append("body = :{}".format(len(params) + 1))
                params.append(body)
            params += [note_id, user_id]
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    "UPDATE notes SET {} WHERE note_id = :{} AND user_id = :{}".format(
                        ", ".join(sets), len(params) - 1, len(params)
                    ),
                    params,
                )
                if cur.rowcount == 0:
                    return {"error": "Note not found"}, 404
            return self.get(user_id, note_id)
        except Exception as e:
            logger.error("notes.update(user=%s, note=%s): %s", user_id, note_id, e)
            return {"error": str(e)}, 500

    def delete(self, user_id: int, note_id: int):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM notes WHERE note_id = :1 AND user_id = :2",
                    [note_id, user_id],
                )
                if cur.rowcount == 0:
                    return {"error": "Note not found"}, 404
            return {"message": "Note deleted"}, 200
        except Exception as e:
            logger.error("notes.delete(user=%s, note=%s): %s", user_id, note_id, e)
            return {"error": str(e)}, 500
