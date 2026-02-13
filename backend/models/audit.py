"""
AuditLog ORM model.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from backend.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    username = Column(String(100))
    user_role = Column(String(50))
    action = Column(String(100), nullable=False)
    details = Column(String)
    status = Column(String(20), default="SUCCESS")
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "log_id": self.log_id,
            "user_id": self.user_id,
            "username": self.username,
            "user_role": self.user_role,
            "action": self.action,
            "details": self.details,
            "status": self.status,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
