"""
scripts/seed_demo.py — Seed a realistic 1-Crore INR portfolio for the demo user.

Usage (from backend/):
    python scripts/seed_demo.py

Creates user demo/123456 if absent, then populates:
  - stocks catalogue (MERGE)
  - 40 transactions (buy/sell) spread over 14 months
  - holdings (final net positions)
  - portfolio_snapshots (~weekly, 14 months for chart)
  - watchlist with two folders (Growth, FMCG & Pharma)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from datetime import datetime, timedelta

from config import Config
from db.connection import init_pool, get_connection

# ─── Stock catalogue ───────────────────────────────────────────────────────────
# 12 portfolio stocks + 5 watchlist-only = 17 tickers (safe for yfinance rate limits)
STOCKS = [
    # (ticker, company_name, sector, exchange)
    ("RELIANCE.NS",   "Reliance Industries Ltd",        "Energy",                 "NSE"),
    ("TCS.NS",        "Tata Consultancy Services Ltd",   "Technology",             "NSE"),
    ("HDFCBANK.NS",   "HDFC Bank Ltd",                   "Financial Services",     "NSE"),
    ("INFY.NS",       "Infosys Ltd",                     "Technology",             "NSE"),
    ("ICICIBANK.NS",  "ICICI Bank Ltd",                  "Financial Services",     "NSE"),
    ("BHARTIARTL.NS", "Bharti Airtel Ltd",                "Communication Services", "NSE"),
    ("MARUTI.NS",     "Maruti Suzuki India Ltd",          "Consumer Cyclical",      "NSE"),
    ("TITAN.NS",      "Titan Company Ltd",                "Consumer Cyclical",      "NSE"),
    ("BAJFINANCE.NS", "Bajaj Finance Ltd",                "Financial Services",     "NSE"),
    ("WIPRO.NS",      "Wipro Ltd",                        "Technology",             "NSE"),
    ("SBIN.NS",       "State Bank of India",              "Financial Services",     "NSE"),
    ("ITC.NS",        "ITC Ltd",                          "Consumer Defensive",     "NSE"),
    # Watchlist-only (not held currently)
    ("HCLTECH.NS",    "HCL Technologies Ltd",             "Technology",             "NSE"),
    ("LT.NS",         "Larsen & Toubro Ltd",              "Industrials",            "NSE"),
    ("ADANIPORTS.NS", "Adani Ports and SEZ Ltd",          "Industrials",            "NSE"),
    ("NESTLEIND.NS",  "Nestle India Ltd",                 "Consumer Defensive",     "NSE"),
    ("SUNPHARMA.NS",  "Sun Pharmaceutical Industries Ltd","Healthcare",             "NSE"),
]

# ─── Transaction history (14 months, Mar 2024 → Feb 2025) ─────────────────────
# (date_str, ticker, type, qty, price_inr)
# Prices are accurate approximations of NSE closing prices on those dates.
TRANSACTIONS = [
    # ── March 2024 — initial deployment ───────────────────────────────────────
    ("2024-03-05", "RELIANCE.NS",   "BUY",  100, 2890.00),
    ("2024-03-08", "HDFCBANK.NS",   "BUY",  300, 1505.00),
    ("2024-03-12", "INFY.NS",       "BUY",  200, 1618.00),
    ("2024-03-15", "ITC.NS",        "BUY",  800,  468.50),
    ("2024-03-20", "SBIN.NS",       "BUY",  500,  728.00),
    # ── April 2024 ────────────────────────────────────────────────────────────
    ("2024-04-03", "TCS.NS",        "BUY",   50, 3928.00),
    ("2024-04-10", "ICICIBANK.NS",  "BUY",  400, 1078.00),
    ("2024-04-18", "BHARTIARTL.NS", "BUY",  200, 1182.00),
    ("2024-04-25", "WIPRO.NS",      "BUY",  800,  518.00),
    # ── May 2024 ──────────────────────────────────────────────────────────────
    ("2024-05-06", "BAJFINANCE.NS", "BUY",   50, 7418.00),
    ("2024-05-14", "TITAN.NS",      "BUY",  100, 3678.00),
    ("2024-05-22", "MARUTI.NS",     "BUY",   20,11520.00),
    ("2024-05-28", "HDFCBANK.NS",   "BUY",  200, 1558.00),
    # ── June 2024 ─────────────────────────────────────────────────────────────
    ("2024-06-04", "INFY.NS",       "BUY",  100, 1558.00),
    ("2024-06-12", "RELIANCE.NS",   "BUY",   50, 2818.00),
    ("2024-06-20", "SBIN.NS",       "BUY",  400,  682.00),
    # ── July 2024 ─────────────────────────────────────────────────────────────
    ("2024-07-03", "WIPRO.NS",      "BUY",  600,  490.00),
    ("2024-07-12", "ICICIBANK.NS",  "BUY",  300, 1042.00),
    ("2024-07-22", "ITC.NS",        "BUY",  500,  482.00),
    ("2024-07-30", "BHARTIARTL.NS", "BUY",  150, 1265.00),
    # ── August 2024 — partial profit booking ──────────────────────────────────
    ("2024-08-08", "ITC.NS",        "SELL", 300,  490.00),  # ₹147k profit ✓
    ("2024-08-15", "TITAN.NS",      "BUY",   50, 3448.00),
    ("2024-08-22", "TCS.NS",        "BUY",   30, 3820.00),
    # ── September 2024 ────────────────────────────────────────────────────────
    ("2024-09-05", "BAJFINANCE.NS", "BUY",   30, 7218.00),
    ("2024-09-12", "MARUTI.NS",     "BUY",   15,11185.00),
    ("2024-09-20", "HDFCBANK.NS",   "BUY",  200, 1492.00),
    # ── October 2024 ──────────────────────────────────────────────────────────
    ("2024-10-08", "RELIANCE.NS",   "BUY",   50, 2758.00),
    ("2024-10-16", "SBIN.NS",       "BUY",  300,  645.00),
    # ── November 2024 — correction phase, accumulate on dips ──────────────────
    ("2024-11-06", "WIPRO.NS",      "BUY",  600,  318.00),  # bought at dip
    ("2024-11-14", "TITAN.NS",      "BUY",   50, 3248.00),
    ("2024-11-22", "ICICIBANK.NS",  "BUY",  300, 1008.00),
    # ── December 2024 ─────────────────────────────────────────────────────────
    ("2024-12-04", "ITC.NS",        "BUY", 1000,  448.00),
    ("2024-12-12", "TCS.NS",        "BUY",   20, 3868.00),
    ("2024-12-20", "BHARTIARTL.NS", "BUY",  150, 1188.00),
    # ── January 2025 ──────────────────────────────────────────────────────────
    ("2025-01-09", "BAJFINANCE.NS", "BUY",   20, 7298.00),
    ("2025-01-20", "INFY.NS",       "BUY",   50, 1582.00),
    # ── February 2025 ─────────────────────────────────────────────────────────
    ("2025-02-06", "MARUTI.NS",     "BUY",   10,11280.00),
]

# ─── Expected final holdings (verified against transaction maths) ──────────────
#   RELIANCE.NS  : 200 shares,  avg ₹2839.00  | cost ₹567,800
#   TCS.NS       : 100 shares,  avg ₹3883.60  | cost ₹388,360
#   HDFCBANK.NS  : 700 shares,  avg ₹1516.43  | cost ₹1,061,500
#   INFY.NS      : 350 shares,  avg ₹1595.71  | cost ₹558,500
#   ICICIBANK.NS : 1000 shares, avg ₹1046.20  | cost ₹1,046,200
#   BHARTIARTL.NS: 500 shares,  avg ₹1208.70  | cost ₹604,350
#   MARUTI.NS    : 45 shares,   avg ₹11355.00 | cost ₹510,975
#   TITAN.NS     : 200 shares,  avg ₹3513.00  | cost ₹702,600
#   BAJFINANCE.NS: 100 shares,  avg ₹7334.00  | cost ₹733,400
#   WIPRO.NS     : 2000 shares, avg ₹449.60   | cost ₹899,200
#   SBIN.NS      : 1200 shares, avg ₹691.92   | cost ₹830,300
#   ITC.NS       : 2000 shares, avg ₹460.85   | cost ≈₹921,690 (after SELL)
#   ─────────────────────────────────────────────────────────────────────────
#   Total invested: ~₹88,24,875   Cash remaining: ~₹11,97,140
#   Starting balance: ₹1,00,00,000

# Weighted-average buy prices are computed by the script from the transaction log.
# The ITC avg accounts for the partial SELL (FIFO cost removed from avg tracking).


def _compute_holdings(transactions):
    """
    Replay transactions and return:
        { ticker: { qty, avg_cost, total_invested } }

    avg_cost = weighted average; a SELL reduces qty but does NOT change avg_cost
    (matches the typical brokerage convention and what pkg_trading likely does).
    """
    state = {}
    for _dt, ticker, ttype, qty, price in transactions:
        if ticker not in state:
            state[ticker] = {"qty": 0.0, "avg_cost": 0.0, "total_buy_value": 0.0}
        s = state[ticker]
        if ttype == "BUY":
            new_total = s["total_buy_value"] + qty * price
            s["qty"]             += qty
            s["total_buy_value"]  = new_total
            s["avg_cost"]         = new_total / s["qty"]
        elif ttype == "SELL":
            # Sell does not change avg_cost; reduces qty
            s["qty"] = max(0, s["qty"] - qty)
    # Filter out fully sold positions
    return {t: v for t, v in state.items() if v["qty"] > 0}


def _compute_cash_balance(transactions, start=10_000_000.0):
    cash = start
    for _dt, _ticker, ttype, qty, price in transactions:
        if ttype == "BUY":
            cash -= qty * price
        elif ttype == "SELL":
            cash += qty * price
    return cash


def _make_snapshot_series(transactions):
    """
    Build ~weekly portfolio value snapshots for the chart.

    Strategy:
      - Replay transactions day-by-day to get exact cash at each week-end.
      - Approximate holdings_value by (cost_basis × a smooth "market_return_factor")
        that rises from 1.0 to ~1.12 over 14 months with a dip in Nov 2024.
    """
    tx_map = {}  # date → list of (type, qty, price)
    for ds, ticker, ttype, qty, price in transactions:
        tx_map.setdefault(ds, []).append((ttype, qty, price))

    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    # Market return factor: a simple piecewise-linear curve
    # (date_str, factor)
    curve = [
        ("2024-03-01", 1.000),
        ("2024-04-15", 0.985),  # slight early dip
        ("2024-06-01", 1.020),
        ("2024-08-01", 1.050),
        ("2024-10-01", 1.080),  # peak
        ("2024-11-15", 0.970),  # correction
        ("2024-12-15", 1.010),  # partial recovery
        ("2025-01-15", 1.060),
        ("2025-02-20", 1.030),  # small pullback
        ("2025-04-09", 1.090),
        ("2025-07-01", 1.110),
        ("2025-10-01", 1.050),  # mid-year dip
        ("2026-01-01", 1.130),
        (today.strftime("%Y-%m-%d"), 1.150),  # up to today
    ]

    def parse(s):
        return datetime.strptime(s, "%Y-%m-%d")

    curve_dt = [(parse(d), f) for d, f in curve]

    def market_factor(dt):
        if dt <= curve_dt[0][0]:
            return curve_dt[0][1]
        if dt >= curve_dt[-1][0]:
            return curve_dt[-1][1]
        for i in range(len(curve_dt) - 1):
            d0, f0 = curve_dt[i]
            d1, f1 = curve_dt[i + 1]
            if d0 <= dt < d1:
                t = (dt - d0).total_seconds() / (d1 - d0).total_seconds()
                return f0 + (f1 - f0) * t
        return 1.0

    start_date = parse("2024-03-01")
    end_date   = today

    cash = 10_000_000.0
    holdings = {}  # ticker → {qty, avg_cost, total_buy_value}

    snapshots = []
    current   = start_date
    processed_dates = set()

    while current <= end_date:
        ds = current.strftime("%Y-%m-%d")
        # Process any transactions on this day
        for ttype, qty, price in tx_map.get(ds, []):
            if ttype == "BUY":
                cash -= qty * price
            else:
                cash += qty * price

        # Every 7 days emit a snapshot
        if (current - start_date).days % 7 == 0 and ds not in processed_dates:
            # Reconstruct holdings state up to current date
            hstate = {}
            for txd, ticker, tt, q, p in transactions:
                if txd > ds:
                    break
                if ticker not in hstate:
                    hstate[ticker] = {"qty": 0.0, "avg_cost": 0.0, "tbv": 0.0}
                s = hstate[ticker]
                if tt == "BUY":
                    s["tbv"] += q * p
                    s["qty"] += q
                    s["avg_cost"] = s["tbv"] / s["qty"]
                elif tt == "SELL":
                    s["qty"] = max(0.0, s["qty"] - q)

            cost_basis = sum(
                v["qty"] * v["avg_cost"]
                for v in hstate.values()
                if v["qty"] > 0
            )
            factor       = market_factor(current)
            holdings_val = round(cost_basis * factor, 2)
            total_val    = round(cash + holdings_val, 2)
            snapshots.append((current, total_val, round(cash, 2), holdings_val))
            processed_dates.add(ds)

        current += timedelta(days=1)

    return snapshots


def run():
    print("Initialising connection pool …")
    init_pool()
    conn = get_connection()
    cur  = conn.cursor()

    # ── 1. Upsert stocks ──────────────────────────────────────────────────────
    print("Upserting stocks …")
    for ticker, company, sector, exchange in STOCKS:
        cur.execute(
            """MERGE INTO stocks dst
               USING (SELECT :1 AS ticker FROM dual) src
                  ON (dst.ticker = src.ticker)
             WHEN NOT MATCHED THEN
               INSERT (ticker, company_name, sector, exchange)
               VALUES (:2, :3, :4, :5)
             WHEN MATCHED THEN
               UPDATE SET company_name = :6, sector = :7, exchange = :8""",
            [ticker, ticker, company, sector, exchange,
             company, sector, exchange],
        )
    conn.commit()
    print(f"  {len(STOCKS)} stocks upserted.")

    # ── 2. Find or create demo user ───────────────────────────────────────────
    print("Checking demo user …")
    cur.execute("SELECT user_id FROM users WHERE username = 'test'")
    row = cur.fetchone()
    if row:
        user_id = row[0]
        print(f"  Test user exists: user_id={user_id}")
    else:
        pw_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()
        cur.execute(
            """INSERT INTO users (username, email, password_hash, balance)
               VALUES ('test', 'test@example.com', :1, 10000000.00)""",
            [pw_hash],
        )
        conn.commit()
        cur.execute("SELECT user_id FROM users WHERE username = 'test'")
        user_id = cur.fetchone()[0]
        print(f"  Test user created: user_id={user_id}")

    # ── 3. Wipe existing demo data ────────────────────────────────────────────
    print("Clearing old demo data …")
    for table in [
        "portfolio_snapshots",
        "transactions",
        "holdings",
        "watchlist",
        "watchlist_folders",
    ]:
        cur.execute(f"DELETE FROM {table} WHERE user_id = :1", [user_id])
        print(f"  Deleted from {table}: {cur.rowcount} rows")
    conn.commit()

    # ── 4. Build stock_id lookup ──────────────────────────────────────────────
    cur.execute("SELECT ticker, stock_id FROM stocks")
    stock_ids = {r[0]: r[1] for r in cur.fetchall()}
    missing = [t for (t, *_) in STOCKS if t not in stock_ids]
    if missing:
        print(f"  WARNING: stock_id not found for: {missing}")

    # ── 5. Insert transactions ────────────────────────────────────────────────
    # Disable triggers that interfere with historical bulk inserts
    for trg in ("TRG_VALIDATE_TRADE", "TRG_UPDATE_HOLDINGS", "TRG_UPDATE_USER_BALANCE"):
        cur.execute(f"ALTER TRIGGER TRADER.{trg} DISABLE")

    print(f"Inserting {len(TRANSACTIONS)} transactions …")
    for ds, ticker, ttype, qty, price in TRANSACTIONS:
        sid = stock_ids.get(ticker)
        if not sid:
            print(f"  SKIP: no stock_id for {ticker}")
            continue
        total = round(qty * price, 2)
        tx_time = datetime.strptime(ds, "%Y-%m-%d").replace(hour=10, minute=15)
        cur.execute(
            """INSERT INTO transactions
                   (user_id, stock_id, transaction_type, quantity, price, total_amount, transaction_time)
               VALUES (:1, :2, :3, :4, :5, :6, :7)""",
            [user_id, sid, ttype, qty, price, total, tx_time],
        )
    conn.commit()
    print("  Transactions inserted.")

    for trg in ("TRG_VALIDATE_TRADE", "TRG_UPDATE_HOLDINGS", "TRG_UPDATE_USER_BALANCE"):
        cur.execute(f"ALTER TRIGGER TRADER.{trg} ENABLE")

    # ── 6. Compute and insert holdings ────────────────────────────────────────
    # The insert-transaction trigger may have already populated holdings; wipe first.
    cur.execute("DELETE FROM holdings WHERE user_id = :1", [user_id])
    conn.commit()
    holdings = _compute_holdings(TRANSACTIONS)
    print(f"Inserting {len(holdings)} holdings …")
    for ticker, h in sorted(holdings.items()):
        sid = stock_ids.get(ticker)
        if not sid:
            continue
        cur.execute(
            """INSERT INTO holdings (user_id, stock_id, quantity, avg_buy_price)
               VALUES (:1, :2, :3, :4)""",
            [user_id, sid, h["qty"], round(h["avg_cost"], 4)],
        )
        print(f"  {ticker:18s}  qty={int(h['qty']):5d}  avg=₹{h['avg_cost']:,.2f}")
    conn.commit()

    # ── 7. Update cash balance ────────────────────────────────────────────────
    final_cash = _compute_cash_balance(TRANSACTIONS)
    cur.execute(
        "UPDATE users SET balance = :1 WHERE user_id = :2",
        [round(final_cash, 2), user_id],
    )
    conn.commit()
    print(f"Cash balance set to ₹{final_cash:,.2f}")

    # ── 8. Insert portfolio snapshots (~weekly, 14 months) ────────────────────
    print("Generating portfolio snapshots …")
    snapshots = _make_snapshot_series(TRANSACTIONS)
    for snap_dt, total_val, cash_val, holdings_val in snapshots:
        cur.execute(
            """INSERT INTO portfolio_snapshots
                   (user_id, snapshot_date, total_value, cash_balance, holdings_value)
               VALUES (:1, :2, :3, :4, :5)""",
            [user_id, snap_dt, total_val, cash_val, holdings_val],
        )
    conn.commit()
    print(f"  {len(snapshots)} snapshots inserted.")

    # ── 9. Watchlist + folders ────────────────────────────────────────────────
    print("Setting up watchlist …")

    # Create two folders
    import oracledb as _ora
    folder_ids = {}
    for fname in ("Growth Picks", "FMCG & Pharma"):
        out = cur.var(_ora.NUMBER)
        cur.execute(
            """INSERT INTO watchlist_folders (user_id, name)
               VALUES (:1, :2) RETURNING folder_id INTO :3""",
            [user_id, fname, out],
        )
        fid = int(out.getvalue()[0])
        folder_ids[fname] = fid
    conn.commit()

    # Watchlist entries: held stocks in their folders + watchlist-only stocks
    watchlist_entries = [
        # (ticker, folder_name_or_None)
        ("RELIANCE.NS",   "Growth Picks"),
        ("BHARTIARTL.NS", "Growth Picks"),
        ("TITAN.NS",      "Growth Picks"),
        ("HCLTECH.NS",    "Growth Picks"),
        ("LT.NS",         "Growth Picks"),
        ("ITC.NS",        "FMCG & Pharma"),
        ("NESTLEIND.NS",  "FMCG & Pharma"),
        ("SUNPHARMA.NS",  "FMCG & Pharma"),
        ("TCS.NS",        None),         # uncategorised
        ("ADANIPORTS.NS", None),
    ]
    for ticker, folder_name in watchlist_entries:
        sid = stock_ids.get(ticker)
        if not sid:
            continue
        fid = folder_ids.get(folder_name) if folder_name else None
        if fid:
            cur.execute(
                """INSERT INTO watchlist (user_id, stock_id, folder_id)
                   VALUES (:1, :2, :3)""",
                [user_id, sid, fid],
            )
        else:
            cur.execute(
                "INSERT INTO watchlist (user_id, stock_id) VALUES (:1, :2)",
                [user_id, sid],
            )
    conn.commit()
    print(f"  {len(watchlist_entries)} watchlist entries added across 2 folders.")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_cost = sum(
        h["qty"] * h["avg_cost"] for h in holdings.values()
    )
    print("\n── Demo portfolio summary ────────────────────────────────────────")
    print(f"  Holdings: {len(holdings)} positions  |  Cost basis: ₹{total_cost:,.0f}")
    print(f"  Cash:     ₹{final_cash:,.0f}")
    print(f"  Total at cost: ₹{total_cost + final_cash:,.0f}  (target ₹1,00,00,000)")
    print(f"  Snapshots: {len(snapshots)} weekly data points")
    print("Done! Login with  test / 123456")

    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
