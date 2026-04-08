"""
routes/watchlist.py — /watchlist  /watchlist/<ticker>
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from utils import get_uid

from services.watchlist_service import WatchlistService

watchlist_bp = Blueprint("watchlist", __name__)
_svc = WatchlistService()


@watchlist_bp.route("/watchlist", methods=["GET"])
@jwt_required()
def get_watchlist():
    user_id = get_uid()
    result, status = _svc.get_watchlist(user_id)
    return jsonify(result), status


@watchlist_bp.route("/watchlist", methods=["POST"])
@jwt_required()
def add_to_watchlist():
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    ticker  = (data.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400

    result, status = _svc.add(user_id, ticker)
    return jsonify(result), status


@watchlist_bp.route("/watchlist/<ticker>", methods=["DELETE"])
@jwt_required()
def remove_from_watchlist(ticker: str):
    user_id = get_uid()
    ticker  = ticker.upper().strip()
    result, status = _svc.remove(user_id, ticker)
    return jsonify(result), status


@watchlist_bp.route("/watchlist/folders", methods=["POST"])
@jwt_required()
def create_folder():
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    name    = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    result, status = _svc.create_folder(user_id, name)
    return jsonify(result), status


@watchlist_bp.route("/watchlist/folders/<int:folder_id>", methods=["PATCH"])
@jwt_required()
def rename_folder(folder_id: int):
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    name    = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    result, status = _svc.rename_folder(user_id, folder_id, name)
    return jsonify(result), status


@watchlist_bp.route("/watchlist/folders/<int:folder_id>", methods=["DELETE"])
@jwt_required()
def delete_folder(folder_id: int):
    user_id = get_uid()
    result, status = _svc.delete_folder(user_id, folder_id)
    return jsonify(result), status


@watchlist_bp.route("/watchlist/<int:watchlist_id>/folder", methods=["PATCH"])
@jwt_required()
def move_item(watchlist_id: int):
    user_id   = int(get_jwt_identity())
    data      = request.get_json(silent=True) or {}
    folder_id = data.get("folder_id")   # None = Uncategorised
    result, status = _svc.move_item(user_id, watchlist_id, folder_id)
    return jsonify(result), status
