"""
Card, CardTransaction, and Merchant ORM models.
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base


class Card(Base):
    __tablename__ = "cards"

    card_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    linked_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    card_type = Column(String(20), nullable=False)
    masked_card_number = Column(String(50), nullable=False)
    expiry_date = Column(Date)
    status = Column(String(20), default="ACTIVE")
    credit_limit = Column(Numeric(15, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="cards")
    linked_account = relationship("Account", back_populates="cards")
    card_transactions = relationship("CardTransaction", back_populates="card")

    def to_dict(self):
        return {
            "card_id": self.card_id,
            "card_type": self.card_type,
            "masked_card_number": self.masked_card_number,
            "status": self.status,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
        }


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_name = Column(String(200), nullable=False)
    category_code = Column(String(50))
    location = Column(String(200))
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)

    card_transactions = relationship("CardTransaction", back_populates="merchant")

    def to_dict(self):
        return {
            "merchant_id": self.merchant_id,
            "merchant_name": self.merchant_name,
            "category_code": self.category_code,
            "location": self.location,
        }


class CardTransaction(Base):
    __tablename__ = "card_transactions"

    card_transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, ForeignKey("cards.card_id", ondelete="CASCADE"), nullable=False)
    merchant_id = Column(Integer, ForeignKey("merchants.merchant_id", ondelete="SET NULL"))
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default="PKR")
    transaction_date = Column(DateTime, nullable=False)
    authorization_status = Column(String(20), default="APPROVED")
    settlement_status = Column(String(20), default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("Card", back_populates="card_transactions")
    merchant = relationship("Merchant", back_populates="card_transactions")

    def to_dict(self):
        return {
            "card_transaction_id": self.card_transaction_id,
            "card_id": self.card_id,
            "merchant_id": self.merchant_id,
            "amount": float(self.amount) if self.amount else 0.0,
            "currency": self.currency,
            "transaction_date": self.transaction_date.isoformat() if self.transaction_date else None,
            "authorization_status": self.authorization_status,
            "settlement_status": self.settlement_status,
        }
