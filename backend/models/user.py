"""
User, Role, UserRole, and Session ORM models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), unique=True, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("UserRole", back_populates="role")

    def to_dict(self):
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "description": self.description,
        }


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200))
    email = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = relationship("UserRole", back_populates="user", lazy="joined")
    sessions = relationship("UserSession", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")

    def get_role_names(self):
        return [ur.role.role_name for ur in self.roles]

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "is_active": self.is_active,
            "roles": self.get_role_names(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserRole(Base):
    __tablename__ = "user_roles"

    user_role_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")
