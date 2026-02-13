"""
Customer, Account, and Branch ORM models.
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base


class Branch(Base):
    __tablename__ = "branches"

    branch_id = Column(Integer, primary_key=True, autoincrement=True)
    branch_code = Column(String(20), unique=True, nullable=False)
    branch_name = Column(String(200), nullable=False)
    branch_type = Column(String(50))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100), default="Pakistan")
    region = Column(String(50))
    opened_date = Column(Date)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="branch")

    def to_dict(self):
        return {
            "branch_id": self.branch_id,
            "branch_code": self.branch_code,
            "branch_name": self.branch_name,
            "branch_type": self.branch_type,
            "city": self.city,
            "region": self.region,
            "status": self.status,
        }


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    address = Column(String)
    email = Column(String(200))
    phone = Column(String(50))
    segment = Column(String(50), default="Retail")
    risk_score = Column(Integer, default=0)
    kyc_status = Column(String(20), default="Verified")
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="customer")
    cards = relationship("Card", back_populates="customer")

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "segment": self.segment,
            "status": self.status,
        }


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(50), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.branch_id", ondelete="SET NULL"))
    account_type = Column(String(50), nullable=False)
    balance = Column(Numeric(15, 2), default=0.00)
    currency = Column(String(10), default="PKR")
    status = Column(String(20), default="Active")
    opening_date = Column(Date)
    last_activity_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="accounts")
    branch = relationship("Branch", back_populates="accounts")
    cards = relationship("Card", back_populates="linked_account")

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "account_number": self.account_number,
            "account_type": self.account_type,
            "balance": float(self.balance) if self.balance else 0.0,
            "currency": self.currency,
            "status": self.status,
        }
