"""
routes/auth.py — /register  /login  /me  /logout
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, create_access_token
from utils import get_uid

from services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__)
_svc = AuthService()


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    result, status = _svc.register(username, email, password)
    return jsonify(result), status


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    result, status = _svc.login(username, password)
    return jsonify(result), status


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_uid()
    result, status = _svc.get_profile(user_id)
    return jsonify(result), status


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    # JWT is stateless; client discards token.
    return jsonify({"message": "Logged out"}), 200
