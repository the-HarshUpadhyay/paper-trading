"""
routes/watchlist.py — /watchlist  /watchlist/<ticker>
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.watchlist_service import WatchlistService

watchlist_bp = Blueprint("watchlist", __name__)
_svc = WatchlistService()


@watchlist_bp.route("/watchlist", methods=["GET"])
@jwt_required()
def get_watchlist():
    user_id = int(get_jwt_identity())
    result, status = _svc.get_watchlist(user_id)
    return jsonify(result), status


@watchlist_bp.route("/watchlist", methods=["POST"])
@jwt_required()
def add_to_watchlist():
    user_id = int(get_jwt_identity())
    data    = request.get_json(silent=True) or {}
    ticker  = (data.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400

    result, status = _svc.add(user_id, ticker)
    return jsonify(result), status


@watchlist_bp.route("/watchlist/<ticker>", methods=["DELETE"])
@jwt_required()
def remove_from_watchlist(ticker: str):
    user_id = int(get_jwt_identity())
    ticker  = ticker.upper().strip()
    result, status = _svc.remove(user_id, ticker)
    return jsonify(result), status
