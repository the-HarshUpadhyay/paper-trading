"""
services/auth_service.py — Registration, login, profile.
"""
import bcrypt
from flask_jwt_extended import create_access_token
import oracledb

from config import Config
from db.connection import DBCursor


class AuthService:

    def register(self, username: str, email: str, password: str):
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            with DBCursor(auto_commit=True) as cur:
                cur.execute(
                    """INSERT INTO users (username, email, password_hash, balance)
                       VALUES (:1, :2, :3, :4)""",
                    [username, email, pw_hash, Config.STARTING_BALANCE]
                )
            return {"message": "Registration successful"}, 201
        except oracledb.IntegrityError as e:
            msg = str(e)
            if "UQ_USERS_USERNAME" in msg.upper():
                return {"error": "Username already taken"}, 409
            if "UQ_USERS_EMAIL" in msg.upper():
                return {"error": "Email already registered"}, 409
            return {"error": "Registration failed"}, 409
        except Exception as e:
            return {"error": str(e)}, 500

    def login(self, username: str, password: str):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT user_id, password_hash, balance, is_active
                         FROM users WHERE username = :1""",
                    [username]
                )
                row = cur.fetchone()
        except Exception as e:
            return {"error": str(e)}, 500

        if not row:
            return {"error": "Invalid credentials"}, 401

        user_id, pw_hash, balance, is_active = row

        if not is_active:
            return {"error": "Account deactivated"}, 403

        if not bcrypt.checkpw(password.encode(), pw_hash.encode()):
            return {"error": "Invalid credentials"}, 401

        token = create_access_token(identity=str(user_id))
        return {
            "token":    token,
            "user_id":  user_id,
            "username": username,
            "balance":  float(balance)
        }, 200

    def get_profile(self, user_id: int):
        try:
            with DBCursor() as cur:
                cur.execute(
                    """SELECT username, email, balance, created_at
                         FROM users WHERE user_id = :1""",
                    [user_id]
                )
                row = cur.fetchone()
        except Exception as e:
            return {"error": str(e)}, 500

        if not row:
            return {"error": "User not found"}, 404

        username, email, balance, created_at = row
        return {
            "user_id":    user_id,
            "username":   username,
            "email":      email,
            "balance":    float(balance),
            "created_at": created_at.isoformat() if created_at else None
        }, 200
