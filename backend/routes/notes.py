from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.notes_service import NotesService
from utils import get_uid

notes_bp = Blueprint("notes", __name__)
_svc = NotesService()


@notes_bp.route("/notes", methods=["GET"])
@jwt_required()
def list_notes():
    user_id = get_uid()
    ticker  = (request.args.get("ticker") or "").strip().upper() or None
    result, status = _svc.list(user_id, ticker)
    return jsonify(result), status


@notes_bp.route("/notes/<int:note_id>", methods=["GET"])
@jwt_required()
def get_note(note_id: int):
    user_id = get_uid()
    result, status = _svc.get(user_id, note_id)
    return jsonify(result), status


@notes_bp.route("/notes", methods=["POST"])
@jwt_required()
def create_note():
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    title   = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    body   = data.get("body") or ""
    ticker = (data.get("ticker") or "").strip() or None
    result, status = _svc.create(user_id, title, body, ticker)
    return jsonify(result), status


@notes_bp.route("/notes/<int:note_id>", methods=["PUT"])
@jwt_required()
def update_note(note_id: int):
    user_id = get_uid()
    data    = request.get_json(silent=True) or {}
    title   = data.get("title")
    body    = data.get("body")
    result, status = _svc.update(user_id, note_id, title, body)
    return jsonify(result), status


@notes_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@jwt_required()
def delete_note(note_id: int):
    user_id = get_uid()
    result, status = _svc.delete(user_id, note_id)
    return jsonify(result), status
