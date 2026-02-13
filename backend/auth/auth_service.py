"""
Authentication service — bcrypt hashing + JWT tokens.
"""

import bcrypt
import jwt
from datetime import datetime, timedelta
from backend.config.settings import Config


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_jwt_token(user_id: int, username: str, roles: list) -> str:
    """Create a JWT token with user info and expiry."""
    payload = {
        "user_id": user_id,
        "username": username,
        "roles": roles,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")


def decode_jwt_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    Returns payload dict or raises jwt.ExpiredSignatureError / jwt.InvalidTokenError.
    """
    return jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
