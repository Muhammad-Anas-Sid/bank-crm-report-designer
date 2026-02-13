"""
Authentication routes — login, token verification, logout.
"""

from flask import Blueprint, request, jsonify, g
from backend.auth.auth_service import verify_password, create_jwt_token
from backend.auth.middleware import jwt_required
from backend.audit.audit_service import AuditService
from backend.models.base import get_db_session
from backend.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user with username + password, return JWT token."""
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password required"}), 400

    session = get_db_session()
    try:
        user = session.query(User).filter(User.username == username, User.is_active == True).first()

        if not user or not verify_password(password, user.password_hash):
            AuditService.log(
                {"user_id": None, "username": username, "roles": []},
                "LOGIN", f"Failed login attempt for '{username}'", "FAILURE",
            )
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        roles = user.get_role_names()
        token = create_jwt_token(user.user_id, user.username, roles)

        user_context = {
            "user_id": user.user_id,
            "username": user.username,
            "roles": roles,
            "full_name": user.full_name,
        }

        AuditService.log_login(user_context, success=True)

        return jsonify({
            "status": "success",
            "token": token,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "full_name": user.full_name,
                "roles": roles,
            },
        })
    finally:
        session.close()


@auth_bp.route("/me", methods=["GET"])
@jwt_required
def get_current_user():
    """Return current user info from JWT token."""
    user = g.current_user
    session = get_db_session()
    try:
        db_user = session.query(User).filter(User.user_id == user["user_id"]).first()
        if not db_user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        return jsonify({
            "user_id": db_user.user_id,
            "username": db_user.username,
            "full_name": db_user.full_name,
            "roles": db_user.get_role_names(),
        })
    finally:
        session.close()


@auth_bp.route("/logout", methods=["POST"])
@jwt_required
def logout():
    """Log the logout action (token invalidation is client-side)."""
    user = g.current_user
    AuditService.log(user, "LOGOUT", "User logged out")
    return jsonify({"status": "success", "message": "Logged out"})
