# PaperTrade — Financial Investment & Portfolio Management System

A production-quality paper trading platform built with **Oracle 19c/XE**, **Python Flask**, and **React**. Practice stock trading with $100,000 in virtual cash, real-time prices via Yahoo Finance, and a clean Zerodha Kite-inspired UI.

---

## Features

- **Authentication** — Register/login with bcrypt-hashed passwords and JWT sessions
- **Stock Search** — Debounced autocomplete with live prices from Yahoo Finance
- **Real-Time Quotes** — Open/High/Low/Close, % change, market cap, P/E ratio
- **Paper Trading** — Buy and sell stocks; PL/SQL triggers enforce all business rules
- **Portfolio Dashboard** — Live P&L, holdings table, portfolio growth chart
- **Watchlist** — Add/remove stocks, track price changes at a glance
- **Order History** — Paginated, immutable transaction ledger
- **Charts** — Line and candlestick charts across 7 time periods
- **Dark / Light Theme** — Toggleable, persisted across sessions
- **Responsive UI** — Collapsible sidebar on mobile

---

## Tech Stack

| Layer      | Technology                               |
|------------|------------------------------------------|
| Database   | Oracle 19c / XE (SQL + PL/SQL)           |
| Backend    | Python 3.11+, Flask, python-oracledb     |
| Auth       | JWT (flask-jwt-extended), bcrypt         |
| Market Data| yfinance (Yahoo Finance)                 |
| Frontend   | React 18, React Router v6, Vite          |
| Charts     | Recharts                                 |
| Icons      | Lucide React                             |

---

## Project Structure

```
paper-trading/
├── database/
│   ├── 01_schema.sql          Tables, indexes, constraints (3NF)
│   ├── 02_triggers.sql        Business-rule enforcement triggers
│   ├── 03_procedures.sql      PL/SQL packages, functions, views
│   └── 04_sample_data.sql     25 stock seeds + demo user
│
├── backend/
│   ├── app.py                 Flask application factory
│   ├── config.py              Configuration (env vars)
│   ├── requirements.txt
│   ├── .env.example
│   ├── db/
│   │   └── connection.py      Oracle connection pool + DBCursor
│   ├── routes/
│   │   ├── auth.py            /register  /login  /me  /logout
│   │   ├── stocks.py          /stocks/search  /stocks/<ticker>  /history
│   │   ├── trading.py         /buy  /sell  /orders
│   │   ├── portfolio.py       /portfolio  /portfolio/snapshots
│   │   └── watchlist.py       /watchlist  (GET/POST/DELETE)
│   └── services/
│       ├── auth_service.py
│       ├── stock_service.py
│       ├── trading_service.py
│       ├── portfolio_service.py
│       └── watchlist_service.py
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx             Router + auth guards
        ├── services/api.js     Axios instance + all API calls
        ├── context/
        │   ├── AuthContext.jsx
        │   └── ThemeContext.jsx
        ├── hooks/
        │   ├── useDebounce.js
        │   └── useLocalStorage.js
        ├── components/
        │   ├── Sidebar.jsx
        │   ├── Header.jsx
        │   ├── StockSearch.jsx
        │   ├── PriceChart.jsx
        │   ├── OrderForm.jsx
        │   └── LoadingSkeleton.jsx
        ├── pages/
        │   ├── Login.jsx
        │   ├── Register.jsx
        │   ├── Dashboard.jsx
        │   ├── StockDetail.jsx
        │   ├── Orders.jsx
        │   └── Watchlist.jsx
        └── styles/
            └── index.css
```

---

## Database Schema

```
USERS               — Registered users with paper-money balance ($100,000 default)
STOCKS              — Stock catalogue (populated on first search/trade)
TRANSACTIONS        — Immutable trade ledger (BUY / SELL)
HOLDINGS            — Live open positions per user (maintained by trigger)
WATCHLIST           — User-specific stock watchlist
PORTFOLIO_SNAPSHOTS — Periodic portfolio valuations for growth chart
```

### PL/SQL Objects

| Object | Type | Purpose |
|---|---|---|
| `trg_validate_trade` | BEFORE INSERT trigger | Blocks oversells; checks cash balance; sets `total_amount` |
| `trg_update_holdings` | AFTER INSERT trigger | Upserts holdings with VWAP cost basis; deletes zero-qty rows |
| `trg_update_user_balance` | AFTER INSERT trigger | Deducts cash on BUY, credits on SELL |
| `trg_stocks_upper_ticker` | BEFORE INSERT/UPDATE trigger | Forces tickers to uppercase |
| `pkg_trading.execute_buy` | Procedure | Validates, resolves stock, inserts transaction |
| `pkg_trading.execute_sell` | Procedure | Validates, inserts transaction |
| `pkg_trading.upsert_stock` | Function | Inserts stock if not in catalogue; returns stock_id |
| `pkg_portfolio.get_portfolio_value` | Function | Returns user's cash balance |
| `pkg_portfolio.save_snapshot` | Procedure | Saves a portfolio valuation snapshot |
| `pkg_portfolio.get_holding_pl` | Function | Calculates P&L for one holding |
| `fn_user_total_invested` | Function | Sum of all open cost bases |
| `vw_user_holdings_detail` | View | Holdings joined with stock info |
| `vw_transaction_history` | View | Transactions joined with stock info |

---

## Setup & Installation

### Prerequisites

- Oracle Database 19c or Oracle XE (with SQL Developer)
- Python 3.11+
- Node.js 18+

---

### 1. Database Setup

Open **Oracle SQL Developer** and run the scripts in order:

```sql
-- 1. Create tables, indexes, constraints
@database/01_schema.sql

-- 2. Create triggers
@database/02_triggers.sql

-- 3. Create packages, procedures, views
@database/03_procedures.sql

-- 4. Insert seed data (25 stocks + demo user)
@database/04_sample_data.sql
```

> **Note:** The demo user `demo_trader` in `04_sample_data.sql` has a placeholder password hash. Register a real account through the UI instead.

---

### 2. Backend Setup

```bash
cd backend

# Copy and fill in environment variables
cp .env.example .env
```

Edit `.env`:

```env
FLASK_DEBUG=1
SECRET_KEY=your-long-random-secret-key

# Oracle connection
ORACLE_USER=your_oracle_username
ORACLE_PASSWORD=your_oracle_password
ORACLE_DSN=localhost:1521/XEPDB1

# JWT
JWT_SECRET_KEY=another-long-random-secret
JWT_ACCESS_TOKEN_EXPIRES=86400
```

Install dependencies and run:

```bash
pip install -r requirements.txt
python app.py
# API running at http://localhost:5000
```

> If using Oracle Instant Client (thick mode), uncomment and set `lib_dir` in [db/connection.py](backend/db/connection.py#L13).

---

### 3. Frontend Setup

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
| POST | `/api/buy` | Execute a buy order `{ticker, quantity, price}` |
| POST | `/api/sell` | Execute a sell order `{ticker, quantity, price}` |
| GET  | `/api/orders?page=1&per_page=20` | Paginated transaction history |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/portfolio` | Holdings with live P&L |
| GET | `/api/portfolio/snapshots?days=30` | Portfolio growth history |

### Watchlist
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/watchlist` | Get all watchlist items with live prices |
| POST   | `/api/watchlist` | Add a ticker `{ticker}` |
| DELETE | `/api/watchlist/<ticker>` | Remove a ticker |

---

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/login` | Login | Username + password sign-in |
| `/register` | Register | New account with $100,000 starting balance |
| `/dashboard` | Dashboard | Portfolio stats, growth chart, holdings table |
| `/stocks/:ticker` | Stock Detail | Live quote, key stats, interactive chart, trade button |
| `/watchlist` | Watchlist | Add/remove stocks, quick trade from list |
| `/orders` | Orders | Full paginated transaction history |

---

## Business Rules

1. **Oversell prevention** — `trg_validate_trade` raises `ORA-20001` if sell quantity exceeds holdings
2. **Insufficient funds** — Same trigger raises `ORA-20002` if cash balance is too low
3. **Immutable ledger** — The `TRANSACTIONS` table is never updated or deleted; holdings are derived from it
4. **VWAP cost basis** — `trg_update_holdings` recalculates average buy price as a volume-weighted average on each new purchase
5. **Portfolio snapshots** — Saved automatically after every trade for the growth chart

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ORACLE_USER` | `system` | Oracle DB username |
| `ORACLE_PASSWORD` | `oracle` | Oracle DB password |
| `ORACLE_DSN` | `localhost:1521/XEPDB1` | Oracle connection string |
| `SECRET_KEY` | — | Flask secret (change in production) |
| `JWT_SECRET_KEY` | — | JWT signing secret (change in production) |
| `JWT_ACCESS_TOKEN_EXPIRES` | `86400` | Token lifetime in seconds (24 hours) |
| `FLASK_DEBUG` | `0` | Enable Flask debug mode |

---

## Production Checklist

- [ ] Set strong `SECRET_KEY` and `JWT_SECRET_KEY` in `.env`
- [ ] Switch Oracle pool credentials to a dedicated app user (not `system`)
- [ ] Run backend with `gunicorn` instead of `python app.py`
- [ ] Build frontend with `npm run build` and serve from a static host or Nginx
- [ ] Enable HTTPS — update `CORS_ORIGINS` in `config.py` accordingly
- [ ] Consider rate-limiting the `/api/stocks/*` endpoints (Yahoo Finance has informal limits)

---

## Screenshots

| Page | Description |
|------|-------------|
| Dashboard | Portfolio value, P&L stats, growth chart, holdings table |
| Stock Detail | Live price, candlestick chart, key statistics, trade modal |
| Watchlist | Live price tracking with quick-trade buttons |
| Orders | Full transaction history with pagination |

---

## License

This project is for educational purposes as part of a **Database Systems Lab** demonstrating Oracle normalization, PL/SQL triggers, stored procedures, and real-time analytics.
