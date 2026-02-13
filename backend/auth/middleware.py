"""
Authentication middleware — JWT verification and RBAC decorators.
"""

from functools import wraps
from flask import request, jsonify, g
from backend.auth.auth_service import decode_jwt_token
import jwt as pyjwt


def jwt_required(f):
    """
    Decorator that requires a valid JWT token in the Authorization header.
    Sets g.current_user with decoded token payload on success.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"status": "error", "message": "Missing or invalid Authorization header"}), 401

        token = auth_header.split("Bearer ", 1)[1].strip()

        try:
            payload = decode_jwt_token(token)
            g.current_user = {
                "user_id": payload["user_id"],
                "username": payload["username"],
                "roles": payload.get("roles", []),
            }
        except pyjwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Token expired. Please login again."}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"status": "error", "message": "Invalid token."}), 401

        return f(*args, **kwargs)

    return decorated


def role_required(*allowed_roles):
    """
    Decorator that enforces RBAC. Must be used AFTER @jwt_required.
    Usage: @role_required("admin", "manager")
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"status": "error", "message": "Authentication required"}), 401

            user_roles = user.get("roles", [])
            if not any(role in allowed_roles for role in user_roles):
                return jsonify({
                    "status": "error",
                    "message": f"Access denied. Required role(s): {', '.join(allowed_roles)}"
                }), 403

            return f(*args, **kwargs)

        return decorated
    return decorator
