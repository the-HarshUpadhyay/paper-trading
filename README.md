# PaperTrade — Financial Investment & Portfolio Management System

A production-quality paper trading platform built with **Oracle 21c XE**, **Python Flask**, and **React**. Practice stock trading with ₹1,00,00,000 in virtual cash, real-time prices via Yahoo Finance, multi-currency support, and a clean Zerodha Kite-inspired UI.

> **Course Context:** Developed as a comprehensive Database Systems Lab project demonstrating Oracle normalization, PL/SQL triggers & stored procedures, constraint-driven data integrity, and real-time analytics — all exposed through a modern three-tier web application.

---

## Table of Contents

1. [Features](#features)
2. [Tech Stack & Architecture Decisions](#tech-stack--architecture-decisions)
3. [System Architecture](#system-architecture)
4. [Project Structure](#project-structure)
5. [Database Design (Deep Dive)](#database-design-deep-dive)
   - [ER Diagram](#er-diagram)
   - [Normalization (3NF)](#normalization-to-3nf)
   - [Core Tables](#core-tables)
   - [Migration Tables](#migration-tables-v2)
   - [Indexing Strategy](#indexing-strategy)
   - [Constraints & Data Integrity](#constraints--data-integrity)
   - [PL/SQL Triggers](#plsql-triggers)
   - [PL/SQL Packages, Procedures & Functions](#plsql-packages-procedures--functions)
   - [Views](#views)
   - [Connection & Pooling](#oracle-connection-pooling)
   - [DB-Backed Price Cache](#db-backed-price-cache)
   - [Migration Strategy](#migration-strategy)
6. [Setup & Installation](#setup--installation)
7. [REST API Reference](#rest-api-reference)
8. [Pages](#pages)
9. [Business Rules](#business-rules)
10. [Background Services](#background-services)
11. [Multi-Currency Support](#multi-currency-support)
12. [Configuration Reference](#configuration-reference)
13. [Known Issues & Potential Bugs](#known-issues--potential-bugs)
14. [Production Checklist](#production-checklist)
15. [Screenshots](#screenshots)
16. [License](#license)

---

## Features

### Core Trading
- **Authentication** — Register/login with bcrypt-hashed passwords and JWT sessions
- **Stock Search** — Debounced autocomplete with live prices from Yahoo Finance; `TickerInput` component reused across Alerts, Watchlist, and Dashboard for consistent ticker entry
- **Real-Time Quotes** — Open/High/Low/Close, % change, market cap, P/E ratio
- **Paper Trading** — Buy and sell stocks; PL/SQL triggers enforce all business rules
- **Portfolio Dashboard** — Live P&L, holdings table, portfolio growth chart

### New Features (v2)
- **Pending / Limit Orders** — Place Limit, Stop, and Stop-Limit orders that auto-fill when the market price hits your target; cancel open orders at any time
- **Price Alerts** — Set ABOVE/BELOW price alerts on any ticker; alerts fire automatically via the background scheduler and generate in-app notifications
- **Notifications** — In-app notification feed; unread count badge in the header; mark-as-read support
- **Trading Notes** — Create, edit, and delete personal notes optionally linked to a specific ticker
- **Analytics Dashboard** — Portfolio growth chart (7D/1M/3M/6M/1Y), sector allocation pie, cash vs. holdings donut, P/L bar chart per holding, top/bottom performer cards
- **Watchlist Folders** — Organise watchlist items into named folders; same ticker can appear in multiple lists; "All" tab shows every watched stock across all lists; add directly to a folder from the add form
- **Multi-Currency / Region Support** — Display all prices and P&L in USD, INR, GBP, EUR, JPY, or HKD; live FX rates fetched daily from Yahoo Finance with hardcoded fallbacks
- **Background Price Scheduler** — Daemon thread (`PriceScheduler`) refreshes active portfolio/watchlist/alert prices every **15 seconds**; checks pending orders and alerts on each tick; saves periodic portfolio snapshots every ~6 minutes
- **Full-Catalogue Price Refresh** — Secondary daemon (`price_refresh`) keeps the entire stock catalogue fresh every **300 seconds** and persists prices to the DB
- **Thread-Safe In-Memory Cache** — `PriceCache` with separate TTLs (30 s price, 60 s full quote); deduplication prevents parallel fetches for the same ticker
- **Health Check Endpoint** — `GET /api/health` returns service status and cache size
- **Watchlist** — Add/remove stocks, track price changes; organised into folders
- **Order History** — Paginated, immutable transaction ledger
- **Charts** — Line and candlestick charts across 7 time periods
- **Dark / Light Theme** — Toggleable, persisted across sessions
- **Responsive UI** — Collapsible sidebar on mobile

---

## Tech Stack & Architecture Decisions

### Technology Choices

| Layer | Technology | Why This Choice |
|-------|-----------|-----------------|
| **Database** | Oracle 21c XE (SQL + PL/SQL) | Enterprise-grade RDBMS with ACID compliance; native support for PL/SQL triggers, stored packages, and `GENERATED ALWAYS AS IDENTITY` columns; `MERGE` for upserts; function-based indexes; and `NUMTODSINTERVAL` for time arithmetic — all critical for a financial system |
| **Backend** | Python 3.12, Flask | Lightweight and flexible; `oracledb` (thin mode) provides zero-dependency Oracle access without Instant Client; Flask blueprints give clean API modularity |
| **Auth** | JWT (`flask-jwt-extended`), `bcrypt` | Stateless auth via signed tokens avoids server-side session storage; bcrypt with auto-generated salts for password hashing |
| **Market Data** | `yfinance` (Yahoo Finance) | Free, no-API-key access to real-time and historical stock data; supports NSE (`.NS` suffix), NYSE, NASDAQ, and global exchanges |
| **FX Rates** | `yfinance` Forex tickers (`USDINR=X`, etc.) | Same library for consistency; daily-cached rates with hardcoded fallbacks for resilience |
| **Frontend** | React 18, React Router v6, Vite | React 18's concurrency model suits high-frequency state updates (live prices); Vite's ESM-native dev server gives sub-second HMR; Router v6 for type-safe nested routing |
| **Charts** | Recharts | Declarative, composable React charting library with responsive container support — ideal for portfolio growth, candlestick, and allocation charts |
| **Icons** | Lucide React | Tree-shakeable icon library, consistent with modern design systems |
| **Dev Infra** | Docker, Docker Compose | Three-service orchestration (Oracle XE + Flask + Vite) with a single command; named volume for DB persistence; healthcheck-based startup ordering |

### Key Architectural Decisions

1. **Database-Driven Business Logic (Triggers over Application Code)**
   Trade validation, holdings maintenance, and balance updates are implemented as Oracle PL/SQL triggers — not in the Python application layer. This ensures data integrity regardless of how the database is accessed (API, SQL*Plus, or another client). The "defense in depth" pattern means even if the Flask app has a bug, the database itself prevents invalid states.

2. **Immutable Transaction Ledger**
   The `TRANSACTIONS` table is append-only — no `UPDATE` or `DELETE` operations ever touch it. Holdings and balances are derived from transactions via triggers, mirroring the event-sourcing pattern used in real financial systems.

3. **Never Fetch Prices in Request Handlers**
   No API endpoint directly calls yfinance. Two background daemon threads (`PriceScheduler` every 15 s, `price_refresh` every 300 s) push prices into an in-memory `PriceCache`. Request handlers read from cache, making portfolio/watchlist responses sub-millisecond. This is achieved via a **stale-while-revalidate** strategy — stale data is served immediately while a background thread refreshes.

4. **Two-Tier Caching (In-Memory + DB)**
   The in-memory `PriceCache` is the hot serving layer (TTL: 30 s basic, 60 s full quote). A `stock_price_cache` table in Oracle persists prices for cross-restart warmup — on startup, entries less than 1 hour old are loaded back into memory so the first requests don't suffer cold-cache misses.

5. **Connection Pooling**
   Oracle connections are expensive to establish. A module-level `oracledb.ConnectionPool` (min=2, max=10) is shared across all threads. The `DBCursor` context manager acquires → auto-commits/rollbacks → releases back to the pool on every operation.

6. **Idempotent Migrations**
   All schema changes beyond the core tables are delivered as numbered migration scripts (`001_notes.sql` through `005_watchlist_multi_folder.sql`) that execute at every backend startup. Each uses Oracle `EXCEPTION WHEN OTHERS` blocks that silently swallow "already exists" errors, making them safe to re-run.

---

## System Architecture

```
┌──────────────┐         ┌──────────────────┐         ┌──────────────────────────────────┐
│              │  HTTP    │                  │ oracledb │                                  │
│   React UI   │◄───────►│   Flask API      │◄────────►│       Oracle 21c XE              │
│   (Vite)     │  /api/* │   (Blueprints)   │  Pool    │   ┌──────────────────────────┐   │
│              │         │                  │ (2-10    │   │ PL/SQL Triggers          │   │
│  ┌────────┐  │         │  ┌────────────┐  │  conns)  │   │  • trg_validate_trade     │   │
│  │Context │  │         │  │ Services   │  │          │   │  • trg_update_holdings    │   │
│  │ Auth   │  │         │  │ Trading    │  │          │   │  • trg_update_user_balance│   │
│  │ Theme  │  │         │  │ Portfolio  │  │          │   │  • trg_stocks_upper_ticker│   │
│  │ Region │  │         │  │ Watchlist  │  │          │   ├──────────────────────────┤   │
│  └────────┘  │         │  │ Alerts     │  │          │   │ PL/SQL Packages          │   │
│              │         │  │ Notes      │  │          │   │  • pkg_trading            │   │
└──────────────┘         │  └────────────┘  │          │   │  • pkg_portfolio          │   │
                         │                  │          │   ├──────────────────────────┤   │
                         │  ┌────────────┐  │          │   │ Views                    │   │
                         │  │ Background │  │          │   │  • vw_user_holdings_detail│   │
                         │  │  Daemons   │  │          │   │  • vw_transaction_history │   │
                         │  │ Scheduler  │──┤          │   └──────────────────────────┘   │
                         │  │ (15s tick) │  │          │                                  │
                         │  │            │  │          │   Tables: USERS, STOCKS,         │
                         │  │ PriceRefr. │  │          │   TRANSACTIONS, HOLDINGS,        │
                         │  │ (300s tick)│  │          │   WATCHLIST, PORTFOLIO_SNAPSHOTS, │
                         │  └────────────┘  │          │   NOTES, WATCHLIST_FOLDERS,       │
                         │                  │          │   PENDING_ORDERS, PRICE_ALERTS,   │
                         │  ┌────────────┐  │          │   NOTIFICATIONS,                  │
                         │  │ PriceCache │  │          │   STOCK_PRICE_CACHE               │
                         │  │ (in-mem)   │  │          │                                  │
                         │  │ TTL: 30/60s│  │          └──────────────────────────────────┘
                         │  └────────────┘  │
                         │                  │
                         │  ┌────────────┐  │
                         │  │  yfinance  │◄─┤  (only from daemon threads, never from
                         │  │  (Yahoo)   │  │   request handlers)
                         │  └────────────┘  │
                         └──────────────────┘
```

**Data Flow (Buy Order):**
```
User clicks BUY → React POST /api/buy → Flask route → TradingService.buy()
  → cur.callproc("pkg_trading.execute_buy", [...])
     → Oracle pkg_trading.execute_buy:
         1. upsert_stock() — INSERT stock if not in catalogue
         2. INSERT INTO transactions — fires BEFORE trigger:
            └── trg_validate_trade — checks balance, computes total_amount
         3. AFTER triggers fire in sequence:
            ├── trg_update_holdings — VWAP upsert into holdings
            └── trg_update_user_balance — deducts cash
         4. COMMIT
  → Flask saves portfolio snapshot (best-effort)
  → HTTP 201 response with transaction details
```

---

## Project Structure

```
paper-trading/
├── docker-compose.yml         Single command to start DB + backend + frontend
├── database/
│   ├── setup.sql              Master script — runs all four files in order
│   ├── 01_schema.sql          Tables, indexes, constraints (3NF)
│   ├── 02_triggers.sql        Business-rule enforcement triggers
│   ├── 03_procedures.sql      PL/SQL packages, functions, views
│   └── 04_sample_data.sql     25 stock seeds + demo user
│
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh          Docker container startup script
│   ├── scripts/
│   │   └── seed_demo.py       Seed demo user + sample portfolio data
│   ├── app.py                 Flask application factory (v2: scheduler, migrations)
│   ├── config.py              Configuration (env vars, starting balance = ₹1,00,00,000)
│   ├── utils.py               Shared helpers (get_uid, scalar_out)
│   ├── requirements.txt
│   ├── .env.example
│   ├── db/
│   │   ├── connection.py      Oracle connection pool + DBCursor context manager
│   │   ├── schema_cache.sql   Cache table DDL
│   │   └── migrations/
│   │       ├── 001_notes.sql           NOTES table
│   │       ├── 002_watchlist_folders.sql  WATCHLIST_FOLDERS + folder_id column
│   │       ├── 003_pending_orders.sql  PENDING_ORDERS table
│   │       ├── 004_alerts.sql          PRICE_ALERTS + NOTIFICATIONS tables
│   │       └── 005_watchlist_multi_folder.sql  Constraint replacement for multi-folder
│   ├── routes/
│   │   ├── auth.py            /register  /login  /me  /logout
│   │   ├── stocks.py          /stocks/search  /stocks/<ticker>  /history
│   │   ├── trading.py         /buy  /sell  /orders
│   │   ├── portfolio.py       /portfolio  /portfolio/snapshots
│   │   ├── watchlist.py       /watchlist  /watchlist/folders  (CRUD + folder ops)
│   │   ├── notes.py           /notes  (CRUD)
│   │   ├── pending_orders.py  /orders/pending  (place, list, cancel)
│   │   └── alerts.py          /alerts  /notifications  (CRUD + mark-read)
│   └── services/
│       ├── auth_service.py
│       ├── stock_service.py
│       ├── trading_service.py
│       ├── portfolio_service.py
│       ├── watchlist_service.py
│       ├── notes_service.py
│       ├── pending_order_service.py   (+ check_and_fill / check_and_fill_all)
│       ├── alert_service.py           (+ check_alerts)
│       ├── cache.py                   PriceCache (thread-safe, TTL-aware)
│       ├── scheduler.py               PriceScheduler daemon (15 s tick)
│       ├── price_refresh.py           Full-catalogue refresh daemon (300 s)
│       ├── market_data.py             yfinance wrapper + batch refresh
│       └── fx_service.py              Daily FX rates (USD/INR/GBP/EUR/JPY/HKD)
│
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx             Router + auth guards
        ├── services/api.js     Axios instance + all API calls
        ├── context/
        │   ├── AuthContext.jsx
        │   ├── ThemeContext.jsx
        │   └── RegionContext.jsx      ← NEW: currency/region state + formatters
        ├── hooks/
        │   ├── useDebounce.js
        │   └── useLocalStorage.js
        ├── components/
        │   ├── Sidebar.jsx
        │   ├── Header.jsx             (notification bell + unread badge)
        │   ├── StockSearch.jsx
        │   ├── TickerInput.jsx        ← NEW: autocomplete ticker search input
        │   ├── PriceChart.jsx
        │   ├── OrderForm.jsx
        │   └── LoadingSkeleton.jsx
        └── pages/
            ├── Login.jsx
            ├── Register.jsx
            ├── Dashboard.jsx
            ├── StockDetail.jsx
            ├── Orders.jsx
            ├── Watchlist.jsx          (+ folder management)
            ├── PendingOrders.jsx      ← NEW
            ├── Alerts.jsx             ← NEW
            ├── Notes.jsx              ← NEW
            └── Analytics.jsx          ← NEW
```

---

## Database Design (Deep Dive)

### ER Diagram

![ER Diagram](er_diagram.png)

---

### Normalization to 3NF

The schema follows **Third Normal Form (3NF)** to eliminate data redundancy and ensure update anomaly-free operations:

| NF | How It Is Enforced |
|----|-------------------|
| **1NF** | Every column stores atomic, single-valued data. No repeating groups or arrays — e.g., each watchlist item is a separate row, not a comma-separated list inside the `users` table. All tables have a defined primary key (`GENERATED ALWAYS AS IDENTITY`). |
| **2NF** | All non-key attributes are fully functionally dependent on the entire primary key. No partial dependencies — composite keys like `(user_id, stock_id)` in `HOLDINGS` have all attributes (quantity, avg_buy_price) dependent on *both* columns together. |
| **3NF** | No transitive dependencies. Stock metadata (`company_name`, `sector`, `exchange`) are stored only in `STOCKS` and referenced via `stock_id` foreign keys in `TRANSACTIONS`, `HOLDINGS`, and `WATCHLIST` — never duplicated. The `total_amount` column in TRANSACTIONS is a computed field (`quantity × price`) set by the `trg_validate_trade` trigger, but is intentionally denormalized for query performance on the immutable ledger. |

**Deliberate Denormalization:**
- `HOLDINGS.avg_buy_price` — Maintained by triggers to avoid recalculating VWAP from the full transaction history on every portfolio query. This is a controlled denormalization; the trigger ensures consistency.
- `PORTFOLIO_SNAPSHOTS` — A time-series projection of portfolio value; inherently denormalized for chart rendering performance.
- `STOCK_PRICE_CACHE` — A materialized cache of external API data; not part of the core transactional schema.

---

### Core Tables

These six tables are created by `01_schema.sql` and form the foundational transactional schema:

#### USERS — User Accounts & Cash Balance
```sql
CREATE TABLE users (
    user_id        NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       VARCHAR2(50)    NOT NULL,
    email          VARCHAR2(100)   NOT NULL,
    password_hash  VARCHAR2(256)   NOT NULL,
    balance        NUMBER(15,2)    DEFAULT 100000.00 NOT NULL,
    created_at     TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    is_active      NUMBER(1)       DEFAULT 1 NOT NULL,
    CONSTRAINT uq_users_username  UNIQUE (username),
    CONSTRAINT uq_users_email     UNIQUE (email),
    CONSTRAINT chk_users_balance  CHECK  (balance >= 0),
    CONSTRAINT chk_users_active   CHECK  (is_active IN (0,1)),
    CONSTRAINT chk_users_email    CHECK  (email LIKE '%@%.%')
);
```
- **Identity column** — `GENERATED ALWAYS AS IDENTITY` makes `user_id` a system-managed surrogate key (no manually specified values allowed) → prevents PK collisions
- **Balance CHECK** — `balance >= 0` is the *last line of defense* against negative balances; the `trg_validate_trade` trigger rejects insufficient funds before this constraint ever fires
- **Email validation** — `CHECK (email LIKE '%@%.%')` provides basic format validation at the database level

#### STOCKS — Stock Catalogue
```sql
CREATE TABLE stocks (
    stock_id      NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker        VARCHAR2(20)    NOT NULL,
    company_name  VARCHAR2(200)   NOT NULL,
    sector        VARCHAR2(100),
    exchange      VARCHAR2(50),
    CONSTRAINT uq_stocks_ticker   UNIQUE (ticker),
    CONSTRAINT chk_stocks_ticker  CHECK  (ticker = UPPER(ticker))
);
```
- Populated lazily on first search or trade via `pkg_trading.upsert_stock()`
- **Uppercase enforcement** — Both a `CHECK` constraint and a `BEFORE INSERT/UPDATE` trigger guarantee tickers are stored in uppercase, preventing duplicate entries like `AAPL` vs `aapl`
- Seeded with 25 NSE-listed Indian stocks (`.NS` suffix for yfinance compatibility)

#### TRANSACTIONS — Immutable Trade Ledger
```sql
CREATE TABLE transactions (
    transaction_id    NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           NUMBER          NOT NULL,
    stock_id          NUMBER          NOT NULL,
    transaction_type  VARCHAR2(4)     NOT NULL,     -- 'BUY' or 'SELL'
    quantity          NUMBER(12,4)    NOT NULL,
    price             NUMBER(15,4)    NOT NULL,
    total_amount      NUMBER(18,4)    NOT NULL,     -- set by trigger
    transaction_time  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT fk_trans_user    FOREIGN KEY (user_id)  REFERENCES users(user_id),
    CONSTRAINT fk_trans_stock   FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    CONSTRAINT chk_trans_type   CHECK (transaction_type IN ('BUY','SELL')),
    CONSTRAINT chk_trans_qty    CHECK (quantity > 0),
    CONSTRAINT chk_trans_price  CHECK (price > 0),
    CONSTRAINT chk_trans_total  CHECK (total_amount > 0)
);
```
- **Event-sourcing design** — This table is **never updated or deleted**; it is an append-only ledger. Every trade is a new row; holdings and balances are *derived* from it via triggers
- `total_amount` is auto-computed by `trg_validate_trade` as `quantity × price`
- Three CHECK constraints prevent nonsensical data (zero/negative quantity, price, or total)

#### HOLDINGS — Live Open Positions
```sql
CREATE TABLE holdings (
    holding_id     NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        NUMBER          NOT NULL,
    stock_id       NUMBER          NOT NULL,
    quantity       NUMBER(12,4)    DEFAULT 0 NOT NULL,
    avg_buy_price  NUMBER(15,4)    DEFAULT 0 NOT NULL,
    last_updated   TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT uq_hold_user_stk  UNIQUE (user_id, stock_id),
    CONSTRAINT chk_hold_qty      CHECK (quantity >= 0),
    CONSTRAINT chk_hold_avg      CHECK (avg_buy_price >= 0)
);
```
- **Trigger-maintained** — Application code never directly INSERTs/UPDATEs this table; all mutations come from `trg_update_holdings` firing after a transaction INSERT
- `UNIQUE (user_id, stock_id)` — One holding row per user/stock pair
- `avg_buy_price` stores the Volume-Weighted Average Price (VWAP) cost basis, recalculated on each purchase
- **Zero-quantity cleanup** — When a user sells 100% of a position, the trigger deletes the holding row entirely

#### WATCHLIST
```sql
CREATE TABLE watchlist (
    watchlist_id  NUMBER    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       NUMBER    NOT NULL,
    stock_id      NUMBER    NOT NULL,
    added_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    folder_id     NUMBER    REFERENCES watchlist_folders(folder_id) ON DELETE SET NULL
);
```
- Initially enforced `UNIQUE(user_id, stock_id)` — migration 005 replaced this with a function-based unique index `(user_id, stock_id, NVL(folder_id, -1))` to allow the same ticker in multiple folders (but not twice in the *same* folder)
- `ON DELETE SET NULL` on `folder_id` means deleting a folder moves its items to the "unfiled" state rather than deleting them

#### PORTFOLIO_SNAPSHOTS — Time-Series Valuations
```sql
CREATE TABLE portfolio_snapshots (
    snapshot_id    NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        NUMBER          NOT NULL,
    total_value    NUMBER(18,2)    NOT NULL,
    cash_balance   NUMBER(15,2)    NOT NULL,
    holdings_value NUMBER(18,2)    NOT NULL,
    snapshot_date  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT chk_snap_total   CHECK (total_value >= 0),
    CONSTRAINT chk_snap_cash    CHECK (cash_balance >= 0),
    CONSTRAINT chk_snap_holdval CHECK (holdings_value >= 0)
);
```
- Saved *after every trade* and periodically every ~6 minutes by the scheduler
- Powers the portfolio growth chart on the Analytics page
- Time-based queries use `NUMTODSINTERVAL(:days, 'DAY')` for correct date arithmetic across DST transitions

---

### Migration Tables (v2)

These tables are auto-applied at every backend startup via numbered, idempotent migration scripts:

| Migration | Table(s) | Purpose | Key Columns |
|-----------|----------|---------|-------------|
| `001_notes.sql` | **NOTES** | Trading journal entries | `note_id PK`, `user_id FK → USERS`, `ticker VARCHAR2(20)`, `title`, `body CLOB`, `created_at`, `updated_at` |
| `002_watchlist_folders.sql` | **WATCHLIST_FOLDERS** | Named folders for watchlist organisation | `folder_id PK`, `user_id FK → USERS`, `name VARCHAR2(100)`, `UNIQUE(user_id, name)` |
| `003_pending_orders.sql` | **PENDING_ORDERS** | Limit/Stop/Stop-Limit orders awaiting execution | `order_id PK`, `user_id FK → USERS`, `stock_id FK → STOCKS`, `order_side CHECK (BUY/SELL)`, `order_type CHECK (LIMIT/STOP/STOP_LIMIT)`, `status CHECK (OPEN/FILLED/CANCELLED/EXPIRED)` |
| `004_alerts.sql` | **PRICE_ALERTS**, **NOTIFICATIONS** | Price threshold alerts and in-app notification feed | `alert_id PK`, `condition CHECK (ABOVE/BELOW)`, `is_active`, `triggered_at`; `notif_id PK`, `alert_id FK → PRICE_ALERTS ON DELETE SET NULL`, `is_read` |
| `005_watchlist_multi_folder.sql` | *(index only)* | Replaces `UNIQUE(user_id, stock_id)` with `UNIQUE(user_id, stock_id, NVL(folder_id,-1))` | Allows the same ticker in different folders |

**Referential Integrity Pattern:**
- `ON DELETE CASCADE` on `user_id` FKs — Deleting a user cleans up all their notes, alerts, notifications, orders, and watchlist items automatically
- `ON DELETE SET NULL` on `alert_id` in NOTIFICATIONS — Preserves notification history even if the alert is deleted
- `ON DELETE SET NULL` on `folder_id` in WATCHLIST — Deleting a folder orphans items into "unfiled" rather than deleting them

---

### Indexing Strategy

Indexes are designed around the application's actual query patterns:

| Index | Table | Columns | Query Pattern |
|-------|-------|---------|---------------|
| `idx_trans_user` | TRANSACTIONS | `(user_id, transaction_time DESC)` | Order history page (paginated, most-recent-first) |
| `idx_trans_stock` | TRANSACTIONS | `(stock_id, transaction_time DESC)` | Per-stock transaction drill-down |
| `idx_trans_user_type` | TRANSACTIONS | `(user_id, transaction_type)` | Filter orders by BUY/SELL type |
| `idx_hold_user` | HOLDINGS | `(user_id)` | Portfolio page (all holdings for a user) |
| `idx_watch_user` | WATCHLIST | `(user_id)` | Watchlist page |
| `idx_snap_user_date` | PORTFOLIO_SNAPSHOTS | `(user_id, snapshot_date DESC)` | Time-series growth chart with date range filter |
| `idx_stocks_name` | STOCKS | `UPPER(company_name)` | **Function-based index** for case-insensitive company name search |
| `idx_notes_user` | NOTES | `(user_id)` | User's notes listing |
| `idx_notes_ticker` | NOTES | `(ticker)` | Filter notes by stock ticker |
| `idx_po_user_status` | PENDING_ORDERS | `(user_id, status)` | List user's open/filled/cancelled orders |
| `idx_po_stock_status` | PENDING_ORDERS | `(stock_id, status)` | Scheduler: find OPEN orders for a given stock |
| `idx_notif_user_unread` | NOTIFICATIONS | `(user_id, is_read)` | Unread notification count badge |
| `idx_alert_ticker` | PRICE_ALERTS | `(ticker, is_active)` | Scheduler: find active alerts for a given ticker |
| `idx_wl_folder` | WATCHLIST | `(folder_id)` | Filter watchlist by folder |
| `idx_wl_user_stk_folder` | WATCHLIST | `(user_id, stock_id, NVL(folder_id,-1))` | **Function-based unique index** — prevents duplicate ticker-folder pairs while allowing same ticker across folders |

> **Design choice:** `DESC` ordering on timestamp indexes for transactions and snapshots avoids expensive `ORDER BY ... DESC` sorts at query time — the optimizer can scan the index in natural order.

---

### Constraints & Data Integrity

The database enforces integrity at five levels:

```
Level 1: NOT NULL          — No mandatory field can be skipped
Level 2: CHECK             — Domain validation (balance ≥ 0, quantity > 0, type ∈ {BUY,SELL})
Level 3: UNIQUE            — No duplicate usernames, emails, tickers, or holdings
Level 4: FOREIGN KEY       — Referential integrity across all relationships
Level 5: TRIGGER           — Complex business rules (oversell prevention, VWAP, balance updates)
```

**Complete constraint inventory:**

| Constraint | Type | Rule |
|-----------|------|------|
| `uq_users_username` | UNIQUE | No duplicate usernames |
| `uq_users_email` | UNIQUE | No duplicate emails |
| `chk_users_balance` | CHECK | `balance >= 0` (last-resort; trigger prevents this pre-emptively) |
| `chk_users_active` | CHECK | `is_active IN (0,1)` — boolean-like flag |
| `chk_users_email` | CHECK | `email LIKE '%@%.%'` — basic email format |
| `uq_stocks_ticker` | UNIQUE | No duplicate ticker symbols |
| `chk_stocks_ticker` | CHECK | `ticker = UPPER(ticker)` — enforces uppercase storage |
| `chk_trans_type` | CHECK | `transaction_type IN ('BUY','SELL')` |
| `chk_trans_qty` | CHECK | `quantity > 0` — no zero-quantity trades |
| `chk_trans_price` | CHECK | `price > 0` — no free stocks |
| `chk_trans_total` | CHECK | `total_amount > 0` |
| `uq_hold_user_stk` | UNIQUE | One holding row per user/stock pair |
| `chk_hold_qty` | CHECK | `quantity >= 0` |
| `chk_hold_avg` | CHECK | `avg_buy_price >= 0` |
| `chk_snap_total/cash/holdval` | CHECK | All snapshot values `>= 0` |
| `uq_wl_folder` | UNIQUE | `(user_id, name)` — no duplicate folder names per user |

---

### PL/SQL Triggers

Four triggers enforce business rules at the database layer:

#### 1. `trg_validate_trade` (BEFORE INSERT on TRANSACTIONS)
```
Purpose: Pre-flight validation for every trade
Fires:   BEFORE INSERT — can modify :NEW row or raise an error to abort
Logic:
  1. Always computes :NEW.total_amount = :NEW.quantity × :NEW.price
  2. On SELL:
     - Queries HOLDINGS for the user's position quantity
     - If owned < requested → RAISE_APPLICATION_ERROR(-20001, 'Insufficient holdings')
  3. On BUY:
     - Queries USERS.balance
     - If balance < required → RAISE_APPLICATION_ERROR(-20002, 'Insufficient balance')
```
> **Why a BEFORE trigger?** — It sets `total_amount` *before* the row is written, and it can abort the INSERT with `RAISE_APPLICATION_ERROR` before any side effects fire.

#### 2. `trg_update_holdings` (AFTER INSERT on TRANSACTIONS)
```
Purpose: Maintain the HOLDINGS table (virtual materialized view)
Fires:   AFTER INSERT — the transaction row is already committed
Logic:
  On BUY:
    - If no holding exists → INSERT new holding (qty = trade qty, avg = trade price)
    - If holding exists → VWAP cost basis recalculation:
        new_qty  = old_qty + buy_qty
        new_avg  = (old_qty × old_avg + buy_qty × buy_price) / new_qty
  On SELL:
    - new_qty = old_qty − sell_qty
    - If new_qty = 0 → DELETE the holding row
    - Otherwise → UPDATE quantity (avg_buy_price is unchanged on sells)
```
> **VWAP formula** — This is the standard Volume-Weighted Average Price calculation used by real brokerages (Zerodha, Groww, etc.) to compute cost basis.

#### 3. `trg_update_user_balance` (AFTER INSERT on TRANSACTIONS)
```
Purpose: Keep the user's cash balance in sync with trades
Logic:
  BUY  → UPDATE users SET balance = balance - total_amount
  SELL → UPDATE users SET balance = balance + total_amount
```

#### 4. `trg_stocks_upper_ticker` (BEFORE INSERT OR UPDATE on STOCKS)
```
Purpose: Normalize ticker symbols to uppercase
Logic:   :NEW.ticker = UPPER(TRIM(:NEW.ticker))
```
> **Belt and suspenders** — The `CHECK (ticker = UPPER(ticker))` constraint would reject lowercase tickers; this trigger *prevents* them from ever reaching the constraint, providing a cleaner user experience (no error).

---

### PL/SQL Packages, Procedures & Functions

#### Package: `pkg_trading`
The public API for all trade execution — called via `cur.callproc()` from Python:

| Member | Type | Signature | Behavior |
|--------|------|-----------|----------|
| `execute_buy` | Procedure | `(p_user_id, p_ticker, p_quantity, p_price, OUT p_trans_id)` | Validates inputs, calls `upsert_stock()` to create catalogue entry if needed, INSERTs into TRANSACTIONS (firing all three triggers), COMMITs, returns `transaction_id` |
| `execute_sell` | Procedure | `(p_user_id, p_ticker, p_quantity, p_price, OUT p_trans_id)` | Same flow but stock must already exist; raises `ORA-20012` if not found |
| `upsert_stock` | Function | `(p_ticker, p_company_name, p_sector?, p_exchange?) RETURN stock_id` | `SELECT stock_id ... EXCEPTION WHEN NO_DATA_FOUND THEN INSERT ... RETURNING stock_id` — idempotent stock registration |

> **Transaction boundary** — Each procedure wraps its logic in `COMMIT` / `ROLLBACK`. This means the PL/SQL layer controls the transaction, not the Python layer — the triggers fire and commit atomically as a single unit of work.

#### Package: `pkg_portfolio`

| Member | Type | Signature | Behavior |
|--------|------|-----------|----------|
| `get_portfolio_value` | Function | `(p_user_id) RETURN NUMBER` | Returns the user's cash balance from the USERS table; holdings value is computed by the Python layer using live prices |
| `save_snapshot` | Procedure | `(p_user_id, p_holdings_val)` | Queries user's balance, INSERTs a snapshot row with `total_value = cash + holdings_val` |
| `get_holding_pl` | Function | `(p_user_id, p_stock_id, p_cur_price) RETURN NUMBER` | Returns `(current_price − avg_buy_price) × quantity` for a single holding |

#### Standalone Function: `fn_user_total_invested`
```sql
-- Returns total cost basis of all open positions
SELECT NVL(SUM(quantity * avg_buy_price), 0) FROM holdings WHERE user_id = p_user_id
```

---

### Views

| View | Joins | Purpose | Query |
|------|-------|---------|-------|
| `vw_user_holdings_detail` | `HOLDINGS ⟕ STOCKS` | Portfolio page — joins stock metadata (ticker, company_name, sector) with position data (quantity, avg_buy_price, cost_basis) | Filters `quantity > 0` to exclude closed positions |
| `vw_transaction_history` | `TRANSACTIONS ⟕ STOCKS` | Order history page — enriches each trade with ticker and company name | Ordered by `transaction_time DESC` |

> These views encapsulate common joins so the Python layer can query them with a simple `SELECT *` instead of writing repetitive SQL.

---

### Oracle Connection Pooling

```python
# db/connection.py — Module-level pool
_pool = oracledb.create_pool(
    user=Config.ORACLE_USER,
    password=Config.ORACLE_PASSWORD,
    dsn=Config.ORACLE_DSN,
    min=2, max=10, increment=1,
)
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `min` | 2 | Always keep 2 warm connections — covers the two background threads (scheduler + price_refresh) |
| `max` | 10 | Ceiling for concurrent API requests; Oracle XE allows ~40 sessions so 10 leaves room for SQL Developer/Admin |
| `increment` | 1 | Grow pool one connection at a time to avoid thundering herd on startup |

The **`DBCursor` context manager** wraps the acquire → execute → commit/rollback → release cycle:

```python
class DBCursor:
    def __init__(self, auto_commit=False): ...
    def __enter__(self) -> oracledb.Cursor:
        self._conn = get_connection()      # Acquire from pool
        self._cursor = self._conn.cursor()
        return self._cursor
    def __exit__(self, exc_type, exc_val, exc_tb):
        if no_error and auto_commit:  self._conn.commit()
        elif error:                   self._conn.rollback()
        self._cursor.close()
        self._conn.close()  # Returns to pool (not a real close)
```

> **Why thin mode?** — `python-oracledb` in thin mode requires zero native libraries, making the Docker image smaller and build faster. Thick mode (Oracle Instant Client) is optional and only needed for features like Advanced Queuing.

---

### DB-Backed Price Cache

A dedicated `STOCK_PRICE_CACHE` table persists price data so the in-memory cache can be warmed from DB on restart:

```sql
CREATE TABLE stock_price_cache (
    ticker          VARCHAR2(20) NOT NULL PRIMARY KEY,
    price           NUMBER(18,4),
    change_pct      NUMBER(10,4),
    open_price      NUMBER(18,4),
    day_high        NUMBER(18,4),
    day_low         NUMBER(18,4),
    previous_close  NUMBER(18,4),
    volume          NUMBER(20),
    market_cap      NUMBER(24),
    fetched_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);
```

**Write strategy:** Uses Oracle `MERGE` (upsert) — `WHEN NOT MATCHED THEN INSERT ... WHEN MATCHED THEN UPDATE` — so the first write for a ticker creates the row, and subsequent writes update it in-place.

**Read strategy:** On startup, rows with `fetched_at > SYSTIMESTAMP - INTERVAL '1' HOUR` are loaded into the in-memory cache, avoiding cold-start latency.

---

### Migration Strategy

Migrations use a pattern compatible with Oracle's PL/SQL exception handling:

```sql
BEGIN
    EXECUTE IMMEDIATE 'CREATE TABLE notes (...)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -955 THEN NULL; END IF;  -- ORA-00955: table already exists
END;
/
```

| Error Code | Meaning | Action |
|-----------|---------|--------|
| `ORA-00955` | Table/index already exists | Silently skip (idempotent) |
| `ORA-01430` | Column already exists (ALTER TABLE ADD) | Silently skip |
| `ORA-02443` | Constraint doesn't exist (DROP CONSTRAINT) | Silently skip |

This pattern allows every migration to run safely on every startup — no migration tracking table is needed. The numbering (`001_` through `005_`) is for human readability and execution ordering.

---

## Setup & Installation

### Option A — Docker Compose (recommended)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# First run — builds images and initialises the database (~2–3 min)
docker compose up --build

# Subsequent runs
docker compose up
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:5000 |
| Oracle | localhost:1521 (XEPDB1) |

The SQL init scripts (`01_schema.sql` → `04_sample_data.sql`) run automatically on first boot. Migration scripts (`001_notes.sql` → `005_watchlist_multi_folder.sql`) are applied automatically every time the backend starts — they are idempotent and safe to re-run. Database state persists in a named Docker volume (`oracle_data`) between restarts.

**Useful commands:**

```bash
# Stop all services
docker compose down

# Stop and wipe the database volume (full reset)
docker compose down -v

# View logs for one service
docker compose logs -f backend
```

> **Note:** The backend waits for the Oracle healthcheck to pass before starting, so the first `docker compose up` will appear to hang for ~2 minutes while Oracle initialises — this is normal.

---

### Option B — Manual Setup

**Prerequisites:**
- Oracle Database 19c or XE (with SQL Developer / SQL*Plus)
- Python 3.12 (3.11+ supported; 3.14 is not — `oracledb` wheels not yet available)
- Node.js 18+

#### 1. Database

Run the master setup script from the project root using SQL*Plus or SQLcl:

```bash
sqlplus your_user/your_pass@localhost:1521/XEPDB1 @database/setup.sql
```

Or open each script in SQL Developer and run them in order:

```sql
@database/01_schema.sql       -- Tables, indexes, constraints
@database/02_triggers.sql     -- Business-rule triggers
@database/03_procedures.sql   -- Packages, procedures, views
@database/04_sample_data.sql  -- 25 stock seeds + demo user
```

> **Note:** The demo user `demo_trader` in `04_sample_data.sql` has a placeholder password hash. Register a real account through the UI instead.
>
> The migration tables (`NOTES`, `WATCHLIST_FOLDERS`, `PENDING_ORDERS`, `PRICE_ALERTS`, `NOTIFICATIONS`) are created automatically when the Flask backend starts for the first time.

#### 2. Backend

```bash
cd backend
cp .env.example .env   # then edit .env with your Oracle credentials
```

```env
FLASK_DEBUG=1
SECRET_KEY=your-long-random-secret-key
ORACLE_USER=trader
ORACLE_PASSWORD=trader
ORACLE_DSN=localhost:1521/XEPDB1
JWT_SECRET_KEY=another-long-random-secret
JWT_ACCESS_TOKEN_EXPIRES=86400
```

```bash
pip install -r requirements.txt
python app.py
# API running at http://localhost:5000
```

> **Oracle Instant Client (thick mode):** uncomment and set `lib_dir` in [db/connection.py](backend/db/connection.py).

#### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# UI running at http://localhost:3000
```

The Vite dev server proxies all `/api/*` requests to `http://localhost:5000`, so no CORS issues during development.

---

## REST API Reference

All endpoints (except `/register` and `/login`) require:
```
Authorization: Bearer <jwt_token>
```

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/register` | Create a new account |
| POST | `/api/login` | Login, returns JWT token |
| GET  | `/api/me` | Get current user profile |
| POST | `/api/logout` | Invalidate session (client-side) |

### Stocks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stocks/search?q=AAPL` | Autocomplete search |
| GET | `/api/stocks/<ticker>` | Live quote + key stats |
| GET | `/api/stocks/<ticker>/history?period=1mo&interval=1d` | OHLCV history |

### Trading
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/buy` | Execute a market buy `{ticker, quantity, price}` |
| POST | `/api/sell` | Execute a market sell `{ticker, quantity, price}` |
| GET  | `/api/orders?page=1&per_page=20` | Paginated transaction history |

### Pending (Limit/Stop) Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/orders/pending` | Place a limit/stop order `{ticker, side, order_type, quantity, limit_price?, stop_price?, expires_at?}` |
| GET    | `/api/orders/pending?status=OPEN` | List pending orders (status: OPEN \| FILLED \| CANCELLED) |
| DELETE | `/api/orders/pending/<order_id>` | Cancel an open order |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/portfolio` | Holdings with live P&L |
| GET | `/api/portfolio/snapshots?days=30` | Portfolio growth history |

### Watchlist
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/watchlist` | Get all watchlist items with live prices + all folders |
| POST   | `/api/watchlist` | Add a ticker `{ticker, folder_id?}` — same ticker allowed in multiple folders |
| DELETE | `/api/watchlist/<ticker>` | Remove all entries for a ticker (full unwatch) |
| DELETE | `/api/watchlist/item/<watchlist_id>` | Remove a single list entry by ID |
| POST   | `/api/watchlist/folders` | Create a folder `{name}` |
| PATCH  | `/api/watchlist/folders/<folder_id>` | Rename a folder `{name}` |
| DELETE | `/api/watchlist/folders/<folder_id>` | Delete a folder |
| PATCH  | `/api/watchlist/<watchlist_id>/folder` | Move item to folder `{folder_id}` |

### Notes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/notes?ticker=AAPL` | List notes (optional ticker filter) |
| GET    | `/api/notes/<note_id>` | Get a single note |
| POST   | `/api/notes` | Create a note `{title, body?, ticker?}` |
| PUT    | `/api/notes/<note_id>` | Update note `{title?, body?}` |
| DELETE | `/api/notes/<note_id>` | Delete a note |

### Alerts & Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/alerts` | List active price alerts |
| POST   | `/api/alerts` | Create an alert `{ticker, condition, target_price}` — condition: `ABOVE` or `BELOW` |
| DELETE | `/api/alerts/<alert_id>` | Delete an alert |
| GET    | `/api/notifications?unread_only=true` | List notifications |
| POST   | `/api/notifications/read` | Mark notifications as read `{ids: [...]}` |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Service status + cache entry count |

---

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/login` | Login | Username + password sign-in |
| `/register` | Register | New account with ₹1,00,00,000 starting balance |
| `/dashboard` | Dashboard | Portfolio stats, growth chart, holdings table |
| `/stocks/:ticker` | Stock Detail | Live quote, key stats, interactive chart, trade button |
| `/watchlist` | Watchlist | Add/remove stocks; organise into folders; quick trade |
| `/orders` | Orders | Full paginated market order history |
| `/pending-orders` | Pending Orders | Limit/Stop orders — place, view status, cancel |
| `/alerts` | Alerts | Set and manage price alerts; view triggered notifications |
| `/notes` | Notes | Personal trading journal; filter by ticker |
| `/analytics` | Analytics | Portfolio analytics — growth chart, sector allocation, P/L breakdown |

---

## Business Rules

1. **Oversell prevention** — `trg_validate_trade` raises `ORA-20001` if sell quantity exceeds holdings
2. **Insufficient funds** — Same trigger raises `ORA-20002` if cash balance is too low
3. **Immutable ledger** — The `TRANSACTIONS` table is never updated or deleted; holdings are derived from it
4. **VWAP cost basis** — `trg_update_holdings` recalculates average buy price as a volume-weighted average on each new purchase
5. **Portfolio snapshots** — Saved after every trade and periodically every ~6 minutes by the scheduler for the growth chart; uses `NUMTODSINTERVAL` for correct date arithmetic on multi-day ranges
6. **Pending order auto-fill** — Every scheduler tick (~15 s), `check_and_fill_all` evaluates all OPEN pending orders against the current cached price and executes the trade when triggered; BUY SL-M triggers when price rises to/above stop; SELL SL-M triggers when price falls to/below stop
7. **Alert one-shot** — Once a price alert fires it is marked `is_active = 0`; a notification row is inserted and the user's unread count increments; alert tickers are included in the scheduler's active ticker list even if not held or watched
8. **Idempotent migrations** — Migration scripts use `CREATE TABLE … IF NOT EXISTS` equivalent patterns so they can be safely re-applied on restart

---

## Background Services

| Service | Class / Function | Interval | What it does |
|---------|-----------------|----------|--------------| 
| Price Scheduler | `PriceScheduler` | 15 s | Fetches prices for active holdings + watchlist + alert tickers; checks pending orders; fires alerts; saves periodic portfolio snapshots every ~6 min |
| Price Refresh Daemon | `start_refresh_daemon` | 300 s | Refreshes the entire stock catalogue; persists prices to DB |
| FX Rate Service | `fx_service.get_rates()` | Daily | Fetches live forex rates from yfinance; used by the region/currency context |

---

## Multi-Currency Support

The frontend `RegionContext` lets users switch display currency. All monetary values are internally stored in the stock's native currency but converted on the fly using the FX service.

Supported regions/currencies:

| Region | Currency | Symbol |
|--------|----------|--------|
| US | USD | $ |
| India | INR | ₹ |
| UK | GBP | £ |
| Europe | EUR | € |
| Japan | JPY | ¥ |
| Hong Kong | HKD | HK$ |

> **Note:** Cash balance is stored in INR by default (based on `STARTING_BALANCE = 1,00,00,000`). The region context converts it to the selected display currency using live daily FX rates.

---

## Configuration Reference

| Variable | Default (manual) | Docker default | Description |
|----------|-----------------|----------------|-------------|
| `ORACLE_USER` | `system` | `trader` | Oracle DB username |
| `ORACLE_PASSWORD` | `oracle` | `trader` | Oracle DB password |
| `ORACLE_DSN` | `localhost:1521/XEPDB1` | `db:1521/XEPDB1` | Oracle connection string |
| `SECRET_KEY` | `dev-secret-change-me` | — | Flask secret (change in production) |
| `JWT_SECRET_KEY` | same as SECRET_KEY | — | JWT signing secret (change in production) |
| `JWT_ACCESS_TOKEN_EXPIRES` | `86400` | `86400` | Token lifetime in seconds (24 hours) |
| `FLASK_DEBUG` | `0` | `1` | Enable Flask debug mode |
| `PRICE_REFRESH_INTERVAL` | `300` | `300` | Full catalogue refresh interval (seconds) |
| `PRICE_STALE_SECONDS` | `600` | `600` | Age threshold before a cached price is considered stale |

When using Docker Compose, `ORACLE_DSN` is automatically overridden to `db:1521/XEPDB1` (using the `db` service name) regardless of what is set in `backend/.env`.

---

## Known Issues & Potential Bugs

> These are documented for awareness and future fixes.

### Backend

1. **`STARTING_BALANCE` mismatch** — `config.py` sets `STARTING_BALANCE = 1_000_000.00` but the auth_service.py INSERT uses `10000000.00`. Ensure `04_sample_data.sql` and any seed `INSERT` statements use the same value, otherwise new accounts created via the UI and seeded demo accounts will have different balances.

2. **`alert_service.mark_read` SQL injection risk (low severity)** — The placeholders string is built via f-string with `len(notif_ids)`. Since the count, not the values, drives the f-string this is safe in practice, but the pattern is fragile. Prefer a fixed `IN (SELECT column_value FROM TABLE(:1))` binding.

3. **`price_cache` singleton shared between Flask workers** — If the backend is later scaled with multiple processes (e.g. gunicorn `--workers N`), each worker will have its own in-memory cache, leading to stale/inconsistent prices across workers. For multi-process deployments, migrate the cache to Redis.

### Frontend

5. **`PriceScheduler` ticker list refreshes every 60 s** — Stocks added to a watchlist or bought within the last 60 s may not be refreshed until the next ticker-list reload. This is by design but can cause temporarily stale prices on newly added items.

---

## Production Checklist

- [ ] Set strong `SECRET_KEY` and `JWT_SECRET_KEY` in `.env`
- [ ] Change the default `trader` / `oracle` database passwords
- [ ] Run backend with `gunicorn` (Linux/macOS) or `waitress` (Windows) — **not** `python app.py`
- [ ] Build frontend with `npm run build` and serve via Nginx or a static host
- [ ] Enable HTTPS — update `CORS_ORIGINS` in `config.py` accordingly
- [ ] Consider rate-limiting `/api/stocks/*` endpoints (Yahoo Finance has informal limits)
- [ ] For multi-process deployments, migrate `PriceCache` to Redis to share state across workers

---

## Screenshots

| Page | Description |
|------|-------------|
| Dashboard | Portfolio value, P&L stats, growth chart, holdings table |
| Stock Detail | Live price, candlestick chart, key statistics, trade modal |
| Watchlist | Live price tracking with folder organisation and quick-trade buttons |
| Orders | Full market order history with pagination |
| Pending Orders | Limit/Stop order management — status tracking, cancel |
| Alerts | Price alert setup and in-app notification feed |
| Notes | Trading journal with optional ticker tagging |
| Analytics | Sector allocation, cash vs. holdings, P/L breakdown, top/bottom performers |

---

## License

This project is for educational purposes as part of a **Database Systems Lab (CSS 2212)** demonstrating Oracle normalization, PL/SQL triggers, stored procedures, and real-time analytics.
