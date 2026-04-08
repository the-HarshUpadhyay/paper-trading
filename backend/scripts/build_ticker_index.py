"""
build_ticker_index.py — One-shot script to regenerate backend/data/tickers.json from yfinance.

Run manually (NOT at startup) when you want to refresh the static ticker index:
    python backend/scripts/build_ticker_index.py

Requires: yfinance, pandas
"""
import json
import os

import yfinance as yf

# S&P 500 component list via Wikipedia table
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

NSE_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "KOTAKBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "ASIANPAINT.NS",
    "ITC.NS", "WIPRO.NS", "AXISBANK.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "NESTLEIND.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "NTPC.NS",
    "ONGC.NS", "COALINDIA.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "JSWSTEEL.NS",
    "HINDALCO.NS", "BAJAJFINSV.NS", "SBILIFE.NS", "HCLTECH.NS", "TECHM.NS",
    "LTIM.NS", "INDUSINDBK.NS", "LT.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "ADANIPOWER.NS", "GRASIM.NS", "DIVISLAB.NS", "DRREDDY.NS", "CIPLA.NS",
    "EICHERMOT.NS", "HEROMOTOCO.NS", "BPCL.NS", "M&M.NS", "TATACONSUM.NS",
    "PIDILITIND.NS", "BRITANNIA.NS", "APOLLOHOSP.NS", "SBIN.NS", "BANKBARODA.NS",
    "FEDERALBNK.NS", "PNB.NS", "CANBK.NS", "HDFCLIFE.NS", "JUBLFOOD.NS",
    "ZOMATO.NS", "NAUKRI.NS", "IRCTC.NS", "HAL.NS", "DMART.NS", "BEL.NS",
]

INDEX_TICKERS = [
    ("^GSPC", "S&P 500"),
    ("^DJI",  "Dow Jones Industrial Average"),
    ("^IXIC", "NASDAQ Composite"),
    ("^NSEI", "NIFTY 50"),
    ("^BSESN","BSE SENSEX"),
    ("^FTSE", "FTSE 100"),
    ("^N225", "Nikkei 225"),
    ("^HSI",  "Hang Seng Index"),
    ("^GDAXI","DAX"),
    ("^FCHI", "CAC 40"),
]


def get_sp500():
    import pandas as pd
    tables = pd.read_html(SP500_URL, header=0)
    df = tables[0]
    return list(zip(df["Symbol"].tolist(), df["Security"].tolist()))


def get_nse_names(tickers):
    result = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            name = info.get("longName") or info.get("shortName") or t
        except Exception:
            name = t
        result.append((t, name))
        print(f"  {t}: {name}")
    return result


def main():
    print("Fetching S&P 500 list from Wikipedia...")
    sp500 = get_sp500()
    print(f"  {len(sp500)} tickers")

    print("Fetching NSE ticker names from yfinance...")
    nse = get_nse_names(NSE_TICKERS)

    entries = []
    # Indices first
    for s, n in INDEX_TICKERS:
        entries.append({"s": s, "n": n})
    # S&P 500
    for s, n in sp500:
        entries.append({"s": s, "n": n})
    # NSE
    for s, n in nse:
        entries.append({"s": s, "n": n})

    # Deduplicate by symbol
    seen = set()
    unique = []
    for e in entries:
        if e["s"] not in seen:
            seen.add(e["s"])
            unique.append(e)

    out_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "tickers.json"
    )
    out_path = os.path.normpath(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, separators=(",", ":"), ensure_ascii=False)

    print(f"\nWrote {len(unique)} entries to {out_path}")


if __name__ == "__main__":
    main()
