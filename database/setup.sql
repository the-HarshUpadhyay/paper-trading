-- ============================================================
--  Paper Trading Platform — Oracle 19c / XE
--  setup.sql  |  Master setup script — runs all SQL files
--
--  Usage (SQL*Plus / SQLcl):
--    sqlplus user/pass@localhost:1521/XEPDB1 @database/setup.sql
--
--  Or from the database/ directory:
--    sqlplus user/pass@localhost:1521/XEPDB1 @setup.sql
--
--  Order of execution:
--    1. 01_schema.sql       — Tables, indexes, constraints
--    2. 02_triggers.sql     — Business-rule triggers
--    3. 03_procedures.sql   — Packages, procedures, views
--    4. 04_sample_data.sql  — Seed / demo data
-- ============================================================

WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK;

PROMPT ============================================================
PROMPT  Paper Trading Platform — Database Setup
PROMPT ============================================================
PROMPT

-- ── Step 1: Schema ────────────────────────────────────────────
PROMPT [1/4] Creating tables, indexes, and constraints...
@@01_schema.sql

-- ── Step 2: Triggers ─────────────────────────────────────────
PROMPT [2/4] Creating triggers...
@@02_triggers.sql

-- ── Step 3: Packages / Procedures / Views ────────────────────
PROMPT [3/4] Creating packages, procedures, and views...
@@03_procedures.sql

-- ── Step 4: Sample data ───────────────────────────────────────
PROMPT [4/4] Inserting sample / seed data...
@@04_sample_data.sql

-- ── Done ──────────────────────────────────────────────────────
PROMPT
PROMPT ============================================================
PROMPT  Setup complete. Database is ready.
PROMPT
PROMPT  Tables created : USERS, STOCKS, TRANSACTIONS,
PROMPT                   HOLDINGS, WATCHLIST, PORTFOLIO_SNAPSHOTS
PROMPT  Triggers       : trg_validate_trade, trg_update_holdings,
PROMPT                   trg_update_user_balance, trg_stocks_upper_ticker
PROMPT  Packages       : pkg_trading, pkg_portfolio
PROMPT  Function       : fn_user_total_invested
PROMPT  Views          : vw_user_holdings_detail, vw_transaction_history
PROMPT  Seed stocks    : 25 tickers loaded
PROMPT  Demo user      : demo_trader / update password via app register
PROMPT ============================================================
