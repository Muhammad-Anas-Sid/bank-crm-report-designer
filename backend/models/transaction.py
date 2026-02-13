"""
Transaction and ExternalAccount ORM models.
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base


class ExternalAccount(Base):
    __tablename__ = "external_accounts"

    external_account_id = Column(Integer, primary_key=True, autoincrement=True)
    account_holder_name = Column(String(200), nullable=False)
    bank_name = Column(String(100), nullable=False)
    iban = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "external_account_id": self.external_account_id,
            "account_holder_name": self.account_holder_name,
            "bank_name": self.bank_name,
            "iban": self.iban,
        }


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_date = Column(DateTime, nullable=False)
    transaction_type = Column(String(50), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    description = Column(String)
    status = Column(String(20), default="POSTED")
    sender_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"))
    receiver_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"))
    external_account_id = Column(Integer, ForeignKey("external_accounts.external_account_id", ondelete="SET NULL"))
    card_id = Column(Integer, ForeignKey("cards.card_id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)

    sender_account = relationship("Account", foreign_keys=[sender_account_id])
    receiver_account = relationship("Account", foreign_keys=[receiver_account_id])
    external_account = relationship("ExternalAccount")
    card = relationship("Card")

    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "transaction_date": self.transaction_date.isoformat() if self.transaction_date else None,
            "transaction_type": self.transaction_type,
            "amount": float(self.amount) if self.amount else 0.0,
            "description": self.description,
            "status": self.status,
            "sender_account_id": self.sender_account_id,
            "receiver_account_id": self.receiver_account_id,
        }
