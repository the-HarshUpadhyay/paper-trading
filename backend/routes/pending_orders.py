from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.pending_order_service import PendingOrderService
from utils import get_uid

pending_orders_bp = Blueprint("pending_orders", __name__)
_svc = PendingOrderService()


@pending_orders_bp.route("/orders/pending", methods=["POST"])
@jwt_required()
def place_order():
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    ticker  = (data.get("ticker") or "").strip().upper()
    side    = (data.get("side") or "").strip().upper()
    otype   = (data.get("order_type") or "").strip().upper()
    qty     = data.get("quantity")
    if not ticker or side not in ("BUY", "SELL") or otype not in ("LIMIT", "STOP", "STOP_LIMIT"):
        return jsonify({"error": "Invalid parameters"}), 400
    try:
        qty = float(qty)
        if qty <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "quantity must be a positive number"}), 400
    limit_price = data.get("limit_price")
    stop_price  = data.get("stop_price")
    expires_at  = data.get("expires_at")
    result, status = _svc.place(user_id, ticker, side, otype, qty, limit_price, stop_price, expires_at)
    return jsonify(result), status


@pending_orders_bp.route("/orders/pending", methods=["GET"])
@jwt_required()
def list_orders():
    user_id = get_uid()
    status  = (request.args.get("status") or "OPEN").upper()
    result, http_status = _svc.list_orders(user_id, status)
    return jsonify(result), http_status


@pending_orders_bp.route("/orders/pending/<int:order_id>", methods=["DELETE"])
@jwt_required()
def cancel_order(order_id: int):
    user_id = get_uid()
    result, status = _svc.cancel(user_id, order_id)
    return jsonify(result), status
