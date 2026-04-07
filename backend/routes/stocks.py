"""
routes/stocks.py — /stocks/search  /stocks/<ticker>  /stocks/<ticker>/history
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from services.stock_service import StockService

stocks_bp = Blueprint("stocks", __name__)
_svc = StockService()


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
