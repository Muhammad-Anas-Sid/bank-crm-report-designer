"""
Chat service — manages chat sessions, messages, and AI greeting logic.
"""

import json
import os
from datetime import datetime
from backend.models.base import get_db_session
from backend.models.chat import ChatSession, ChatMessage
from backend.config.settings import Config


class ChatService:
    """Service for AI chat session and message management."""

    AVAILABLE_DOMAINS = [
        {
            "name": "Card Management System",
            "description": "Cards, card transactions, merchants",
            "entities": ["cards", "card_transactions", "merchants"],
        },
        {
            "name": "Transaction Management System",
            "description": "Transactions, external accounts",
            "entities": ["transactions", "external_accounts"],
        },
    ]

    SHARED_ENTITIES = ["customers", "accounts", "branches"]

    @staticmethod
    def get_greeting(username: str) -> str:
        """Generate the AI greeting message for a user."""
        return f"Hello {username}, what report would you like to generate today?"

    @staticmethod
    def get_domain_info() -> dict:
        """Return available domains and shared entities."""
        return {
            "domains": ChatService.AVAILABLE_DOMAINS,
            "shared_entities": ChatService.SHARED_ENTITIES,
        }

    @staticmethod
    def get_schema_entities() -> dict:
        """Fetch available entities and attributes dynamically from schema metadata."""
        try:
            if os.path.exists(Config.SCHEMA_METADATA_PATH):
                with open(Config.SCHEMA_METADATA_PATH, "r") as f:
                    data = json.load(f)
                    return data.get("tables", data)
        except Exception as e:
            print(f"Error loading schema metadata: {e}")
        return {}

    @staticmethod
    def create_session(user_id: int, title: str = "New Chat") -> dict:
        """Create a new chat session for a user."""
        session = get_db_session()
        try:
            chat_session = ChatSession(
                user_id=user_id,
                title=title,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)
            return chat_session.to_dict()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def get_user_sessions(user_id: int) -> list:
        """Get all chat sessions for a user, ordered by most recent."""
        session = get_db_session()
        try:
            sessions = (
                session.query(ChatSession)
                .filter(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc())
                .all()
            )
            return [s.to_dict() for s in sessions]
        finally:
            session.close()

    @staticmethod
    def add_message(chat_session_id: int, role: str, content: str, message_metadata: dict = None) -> dict:
        """Add a message to a chat session."""
        session = get_db_session()
        try:
            message = ChatMessage(
                chat_session_id=chat_session_id,
                role=role,
                content=content,
                message_metadata=message_metadata,
                created_at=datetime.utcnow(),
            )
            session.add(message)

            # Update session's updated_at
            chat_session = session.query(ChatSession).filter(
                ChatSession.chat_session_id == chat_session_id
            ).first()
            if chat_session:
                chat_session.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(message)
            return message.to_dict()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def get_session_messages(chat_session_id: int) -> list:
        """Get all messages in a chat session, ordered chronologically."""
        session = get_db_session()
        try:
            messages = (
                session.query(ChatMessage)
                .filter(ChatMessage.chat_session_id == chat_session_id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )
            return [m.to_dict() for m in messages]
        finally:
            session.close()

    @staticmethod
    def update_session_title(chat_session_id: int, title: str):
        """Update a chat session's title."""
        session = get_db_session()
        try:
            chat_session = session.query(ChatSession).filter(
                ChatSession.chat_session_id == chat_session_id
            ).first()
            if chat_session:
                chat_session.title = title
                chat_session.updated_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def delete_session(chat_session_id: int):
        """Delete a chat session and all its messages."""
        session = get_db_session()
        try:
            # Delete messages first
            session.query(ChatMessage).filter(
                ChatMessage.chat_session_id == chat_session_id
            ).delete()

            # Delete the session itself
            session.query(ChatSession).filter(
                ChatSession.chat_session_id == chat_session_id
            ).delete()

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
