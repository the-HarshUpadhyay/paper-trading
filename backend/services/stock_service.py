"""
services/stock_service.py — Yahoo Finance integration via yfinance.
Handles search, live quote, and historical OHLCV data.
"""
from __future__ import annotations
import yfinance as yf
import pandas as pd

from db.connection import DBCursor


class StockService:

    # ── Search ─────────────────────────────────────────────────────────────
    def search(self, query: str) -> list[dict]:
        """
        Search DB catalogue first (instant), then fall back to yfinance Ticker.
        Returns list of {ticker, company_name, sector, exchange, price, change_pct}.
        """
        results = []

        # 1. DB catalogue (prefix match on ticker or company name)
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT ticker, company_name, sector, exchange
                         FROM stocks
                        WHERE UPPER(ticker)       LIKE UPPER(:1) || '%'
                           OR UPPER(company_name) LIKE '%' || UPPER(:2) || '%'
                        ORDER BY ticker
                        FETCH FIRST 10 ROWS ONLY""",
                    [query, query]
                )
                rows = cur.fetchall()

            for ticker, name, sector, exchange in rows:
                results.append({
                    "ticker":       ticker,
                    "company_name": name,
                    "sector":       sector or "",
                    "exchange":     exchange or "",
                })
        except Exception:
            pass

        # 2. Enrich with live price (batch fetch for up to 10 tickers)
        if results:
            tickers_str = " ".join(r["ticker"] for r in results)
            try:
                data = yf.download(
                    tickers_str, period="2d", interval="1d",
                    auto_adjust=True, progress=False
                )
                for r in results:
                    t = r["ticker"]
                    try:
                        if isinstance(data.columns, pd.MultiIndex):
                            # yfinance >= 0.2.40: MultiIndex is (price, ticker)
                            closes = data["Close"][t].dropna()
                        else:
                            # Single ticker — flat columns
                            closes = data["Close"].dropna()
                        if len(closes) >= 2:
                            r["price"]      = round(float(closes.iloc[-1]), 4)
                            r["change_pct"] = round(
                                (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2
                            )
                        elif len(closes) == 1:
                            r["price"]      = round(float(closes.iloc[-1]), 4)
                            r["change_pct"] = 0.0
                        else:
                            r["price"] = r["change_pct"] = None
                    except Exception:
                        r["price"] = r["change_pct"] = None
            except Exception:
                for r in results:
                    r["price"] = r["change_pct"] = None

        # 3. If query looks like a raw ticker not in DB, try yfinance directly
        #    Try with .NS suffix (NSE India) if the plain ticker fails
        if not results and len(query) <= 15:
            base = query.upper().rstrip(".")
            for try_ticker in [base, f"{base}.NS", f"{base}.BO"]:
                try:
                    info = yf.Ticker(try_ticker).info
                    if info.get("symbol"):
                        results.append({
                            "ticker":       info["symbol"],
                            "company_name": info.get("longName") or info["symbol"],
                            "sector":       info.get("sector", ""),
                            "exchange":     info.get("exchange", ""),
                            "price":        info.get("currentPrice") or info.get("regularMarketPrice"),
                            "change_pct":   None,
                        })
                        break
                except Exception:
                    pass

        return results

    # ── Live Quote ──────────────────────────────────────────────────────────
    def get_quote(self, ticker: str) -> tuple[dict, int]:
        try:
            info = yf.Ticker(ticker).info
            if not info or not info.get("symbol"):
                return {"error": f"Ticker '{ticker}' not found"}, 404

            price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
            )

            result = {
                "ticker":           info.get("symbol", ticker),
                "company_name":     info.get("longName") or info.get("shortName", ticker),
                "sector":           info.get("sector", ""),
                "industry":         info.get("industry", ""),
                "exchange":         info.get("exchange", ""),
                "price":            price,
                "open":             info.get("open") or info.get("regularMarketOpen"),
                "day_high":         info.get("dayHigh") or info.get("regularMarketDayHigh"),
                "day_low":          info.get("dayLow") or info.get("regularMarketDayLow"),
                "previous_close":   info.get("previousClose"),
                "volume":           info.get("volume") or info.get("regularMarketVolume"),
                "market_cap":       info.get("marketCap"),
                "pe_ratio":         info.get("trailingPE"),
                "52w_high":         info.get("fiftyTwoWeekHigh"),
                "52w_low":          info.get("fiftyTwoWeekLow"),
                "avg_volume":       info.get("averageVolume"),
                "description":      info.get("longBusinessSummary", ""),
            }

            # Calculate % change
            if price and info.get("previousClose"):
                result["change_pct"] = round(
                    (price - info["previousClose"]) / info["previousClose"] * 100, 2
                )
            else:
                result["change_pct"] = None

            # Upsert into DB catalogue
            self._upsert_stock(
                result["ticker"],
                result["company_name"],
                result["sector"],
                result["exchange"]
            )
            return result, 200

        except Exception as e:
            return {"error": str(e)}, 500

    # ── Historical OHLCV ────────────────────────────────────────────────────
    def get_history(self, ticker: str, period: str, interval: str) -> tuple[dict, int]:
        valid_periods   = {"1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"}
        valid_intervals = {"1m","2m","5m","15m","30m","60m","90m","1h","1d","5d","1wk","1mo","3mo"}
        if period   not in valid_periods:   period   = "1mo"
        if interval not in valid_intervals: interval = "1d"

        try:
            df: pd.DataFrame = yf.download(
                ticker, period=period, interval=interval,
                auto_adjust=True, progress=False
            )
            if df.empty:
                return {"error": f"No data for '{ticker}'"}, 404

            df = df.dropna()
            df.index = df.index.tz_localize(None)  # Remove tz for JSON

            # Flatten MultiIndex columns if present (yfinance batch download)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            records = []
            for ts, row in df.iterrows():
                records.append({
                    "time":   ts.isoformat(),
                    "open":   round(float(row["Open"]),  4),
                    "high":   round(float(row["High"]),  4),
                    "low":    round(float(row["Low"]),   4),
                    "close":  round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]) if "Volume" in row else 0,
                })

            return {"ticker": ticker, "period": period, "interval": interval, "data": records}, 200

        except Exception as e:
            return {"error": str(e)}, 500

    # ── Internal helpers ────────────────────────────────────────────────────
    def _upsert_stock(self, ticker, company_name, sector, exchange):
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """MERGE INTO stocks dst
                       USING (SELECT :1 AS ticker FROM dual) src
                          ON (dst.ticker = src.ticker)
                     WHEN NOT MATCHED THEN
                       INSERT (ticker, company_name, sector, exchange)
                       VALUES (:2, :3, :4, :5)
                     WHEN MATCHED THEN
                       UPDATE SET company_name = :6, sector = :7, exchange = :8""",
                    [ticker, ticker, company_name, sector or "", exchange or "",
                     company_name, sector or "", exchange or ""]
                )
        except Exception:
            pass  # DB upsert is best-effort; don't crash the API call
