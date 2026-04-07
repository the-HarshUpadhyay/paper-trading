"""
routes/trading.py — /buy  /sell  /orders
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.trading_service import TradingService

trading_bp = Blueprint("trading", __name__)
_svc = TradingService()


@trading_bp.route("/buy", methods=["POST"])
@jwt_required()
def buy():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    ticker   = (data.get("ticker") or "").strip().upper()
    quantity = data.get("quantity")
    price    = data.get("price")

    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    try:
        quantity = float(quantity)
        price    = float(price)
    except (TypeError, ValueError):
        return jsonify({"error": "quantity and price must be numbers"}), 400
    if quantity <= 0 or price <= 0:
        return jsonify({"error": "quantity and price must be positive"}), 400

    result, status = _svc.buy(user_id, ticker, quantity, price)
    return jsonify(result), status


@trading_bp.route("/sell", methods=["POST"])
@jwt_required()
def sell():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    ticker   = (data.get("ticker") or "").strip().upper()
    quantity = data.get("quantity")
    price    = data.get("price")

    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    try:
        quantity = float(quantity)
        price    = float(price)
    except (TypeError, ValueError):
        return jsonify({"error": "quantity and price must be numbers"}), 400
    if quantity <= 0 or price <= 0:
        return jsonify({"error": "quantity and price must be positive"}), 400

    result, status = _svc.sell(user_id, ticker, quantity, price)
    return jsonify(result), status


@trading_bp.route("/orders", methods=["GET"])
@jwt_required()
def orders():
    user_id = get_jwt_identity()
    page    = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result, status = _svc.get_orders(user_id, page, per_page)
    return jsonify(result), status
