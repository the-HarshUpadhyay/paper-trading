"""
config.py — Application configuration loaded from environment variables.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Flask ──────────────────────────────────────────────
    SECRET_KEY     = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DEBUG          = os.getenv("FLASK_DEBUG", "0") == "1"

    # ── Oracle ─────────────────────────────────────────────
    ORACLE_USER     = os.getenv("ORACLE_USER", "system")
    ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "oracle")
    ORACLE_DSN      = os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1")

    # ── JWT ────────────────────────────────────────────────
    JWT_SECRET_KEY             = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES   = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "86400"))
    )
    JWT_TOKEN_LOCATION         = ["headers"]
    JWT_HEADER_NAME            = "Authorization"
    JWT_HEADER_TYPE            = "Bearer"

    # ── CORS ───────────────────────────────────────────────
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── Misc ───────────────────────────────────────────────
    STARTING_BALANCE = 1_000_000.00
