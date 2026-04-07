"""
db/connection.py — Oracle connection pool using python-oracledb (drop-in cx_Oracle replacement).
"""
import oracledb
from config import Config

# Module-level pool — created once at startup
_pool: oracledb.ConnectionPool | None = None


def init_pool() -> None:
    """Create the Oracle connection pool. Call once from app.py."""
    global _pool
    _pool = oracledb.create_pool(
        user=Config.ORACLE_USER,
        password=Config.ORACLE_PASSWORD,
        dsn=Config.ORACLE_DSN,
        min=2,
        max=10,
        increment=1,
        # Thick mode: set lib_dir if using Oracle Instant Client
        # oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient")
    )


def get_connection() -> oracledb.Connection:
    """Acquire a connection from the pool."""
    if _pool is None:
        raise RuntimeError("Connection pool not initialised. Call init_pool() first.")
    return _pool.acquire()


def close_pool() -> None:
    """Gracefully close all pooled connections."""
    global _pool
    if _pool:
        _pool.close()
        _pool = None


class DBCursor:
    """Context manager that acquires a connection + cursor and auto-commits/rolls back."""

    def __init__(self, auto_commit: bool = False):
        self.auto_commit = auto_commit
        self._conn = None
        self._cursor = None

    def __enter__(self) -> oracledb.Cursor:
        self._conn   = get_connection()
        self._cursor = self._conn.cursor()
        return self._cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self.auto_commit:
            self._conn.commit()
        elif exc_type is not None:
            self._conn.rollback()
        self._cursor.close()
        self._conn.close()   # Returns connection to pool
        return False          # Re-raise any exception
