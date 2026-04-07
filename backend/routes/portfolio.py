"""
routes/portfolio.py — /portfolio  /portfolio/snapshot
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.portfolio_service import PortfolioService

portfolio_bp = Blueprint("portfolio", __name__)
_svc = PortfolioService()


@portfolio_bp.route("/portfolio", methods=["GET"])
@jwt_required()
def get_portfolio():
    user_id = int(get_jwt_identity())
    result, status = _svc.get_portfolio(user_id)
    return jsonify(result), status


@portfolio_bp.route("/portfolio/snapshots", methods=["GET"])
@jwt_required()
def get_snapshots():
    user_id = int(get_jwt_identity())
    days    = int(request.args.get("days", 30))
    result, status = _svc.get_snapshots(user_id, days)
    return jsonify(result), status
