from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.alert_service import AlertService
from utils import get_uid

alerts_bp = Blueprint("alerts", __name__)
_svc = AlertService()


@alerts_bp.route("/alerts", methods=["POST"])
@jwt_required()
def create_alert():
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    ticker  = (data.get("ticker") or "").strip().upper()
    condition = (data.get("condition") or "").strip().upper()
    target_price = data.get("target_price")
    if not ticker or condition not in ("ABOVE", "BELOW"):
        return jsonify({"error": "ticker and condition (ABOVE|BELOW) required"}), 400
    try:
        target_price = float(target_price)
        if target_price <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "target_price must be positive"}), 400
    result, status = _svc.create(user_id, ticker, condition, target_price)
    return jsonify(result), status


@alerts_bp.route("/alerts", methods=["GET"])
@jwt_required()
def list_alerts():
    user_id = get_uid()
    result, status = _svc.list_alerts(user_id)
    return jsonify(result), status


@alerts_bp.route("/alerts/<int:alert_id>", methods=["DELETE"])
@jwt_required()
def delete_alert(alert_id: int):
    user_id = get_uid()
    result, status = _svc.delete(user_id, alert_id)
    return jsonify(result), status


@alerts_bp.route("/notifications", methods=["GET"])
@jwt_required()
def list_notifications():
    user_id    = int(get_jwt_identity())
    unread_only = request.args.get("unread_only", "true").lower() != "false"
    result, status = _svc.list_notifications(user_id, unread_only)
    return jsonify(result), status


@alerts_bp.route("/notifications/read", methods=["POST"])
@jwt_required()
def mark_read():
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    ids     = data.get("ids") or []
    result, status = _svc.mark_read(user_id, [int(i) for i in ids])
    return jsonify(result), status
