"""
routes/stocks.py — /stocks/tickers  /stocks/search  /stocks/<ticker>  /stocks/<ticker>/history
                   /stocks/index/<ticker>
"""
import os
import json
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required

from services.stock_service import StockService
from services.market_data import get_full_quote
from services.fx_service import get_rates

stocks_bp = Blueprint("stocks", __name__)
_svc = StockService()

_TICKERS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json")
_TICKERS_PATH = os.path.normpath(_TICKERS_PATH)


@stocks_bp.route("/stocks/tickers", methods=["GET"])
def get_tickers():
    resp = send_file(_TICKERS_PATH, mimetype="application/json")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@stocks_bp.route("/currency/rates", methods=["GET"])
def currency_rates():
    """Return today's FX rates relative to USD. No auth required."""
    return jsonify(get_rates()), 200


@stocks_bp.route("/stocks/index/<ticker>", methods=["GET"])
def get_index_quote(ticker: str):
    ticker = ticker.upper().strip()
    data = get_full_quote(ticker)
    safe = {
        "ticker":     data.get("ticker", ticker),
        "price":      data.get("price", 0.0),
        "change_pct": data.get("change_pct", 0.0),
        "company_name": data.get("company_name", ticker),
    }
    return jsonify(safe), 200


@stocks_bp.route("/stocks/search", methods=["GET"])
@jwt_required()
def search():
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 1:
        return jsonify([]), 200

    results = _svc.search(q)
    return jsonify(results), 200


@stocks_bp.route("/stocks/<ticker>", methods=["GET"])
@jwt_required()
def get_stock(ticker: str):
    ticker = ticker.upper().strip()
    result, status = _svc.get_quote(ticker)
    return jsonify(result), status


@stocks_bp.route("/stocks/<ticker>/history", methods=["GET"])
@jwt_required()
def get_history(ticker: str):
    ticker = ticker.upper().strip()
    period   = request.args.get("period", "1mo")    # 1d 5d 1mo 3mo 6mo 1y 2y 5y
    interval = request.args.get("interval", "1d")   # 1m 5m 15m 1h 1d 1wk
    result, status = _svc.get_history(ticker, period, interval)
    return jsonify(result), status
