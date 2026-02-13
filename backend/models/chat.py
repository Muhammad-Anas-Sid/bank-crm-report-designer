"""
ChatSession and ChatMessage ORM models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    chat_session_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="New Chat")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session", order_by="ChatMessage.created_at")

    def to_dict(self):
        return {
            "chat_session_id": self.chat_session_id,
            "user_id": self.user_id,
            "title": self.title,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.chat_session_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    message_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    chat_session = relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "chat_session_id": self.chat_session_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.message_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
