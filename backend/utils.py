"""
utils.py — Shared helpers for Flask routes and services.
"""
from flask_jwt_extended import get_jwt_identity


def get_uid() -> int:
    """
    Return the authenticated user's ID as an int.

    flask-jwt-extended v4 may decode the JWT subject as a list when the token
    was created with certain serialization settings.  This helper normalises
    both cases (str "42", list ["42"]) so every route gets a plain int.
    """
    identity = get_jwt_identity()
    if isinstance(identity, (list, tuple)):
        identity = identity[0]
    return int(identity)


def scalar_out(var) -> int:
    """
    Extract a scalar int from an oracledb OUT variable.

    python-oracledb's var.getvalue() returns a list when used with
    RETURNING INTO clauses in DML statements.  This helper normalises
    both the scalar and list cases.
    """
    val = var.getvalue()
    if isinstance(val, (list, tuple)):
        val = val[0]
    return int(val)
