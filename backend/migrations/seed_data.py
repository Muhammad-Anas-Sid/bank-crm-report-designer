import sys
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to sys.path so we can import backend packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.models.base import get_db_session, Base
# Clear metadata to prevent "Table 'sessions' is already defined" error if models are re-imported
Base.metadata.clear()

from backend.models.user import User, Role, UserRole
from backend.models.banking import Branch, Customer, Account
from backend.models.card import Card, Merchant, CardTransaction
from backend.models.transaction import Transaction, ExternalAccount
from backend.models.chat import ChatSession, ChatMessage
from backend.auth.auth_service import hash_password


def seed_roles(session):
    """Create default roles: admin, analyst, manager."""
    roles_data = [
        {"role_name": "admin", "description": "Full access administrator"},
        {"role_name": "analyst", "description": "Data analyst — read and generate reports"},
        {"role_name": "manager", "description": "Branch manager — reports and team management"},
    ]
    for rd in roles_data:
        existing = session.query(Role).filter(Role.role_name == rd["role_name"]).first()
        if not existing:
            session.add(Role(**rd))
    session.commit()
    print("  ✓ Roles seeded")


def seed_users(session):
    """Create demo users with bcrypt-hashed passwords."""
    users_data = [
        {"username": "admin", "password": "admin123", "full_name": "Admin User", "email": "admin@bank.com", "role": "admin"},
        {"username": "analyst_joy", "password": "analyst123", "full_name": "Joy Anderson", "email": "joy@bank.com", "role": "analyst"},
        {"username": "manager_bob", "password": "manager123", "full_name": "Bob Williams", "email": "bob@bank.com", "role": "manager"},
    ]

    for ud in users_data:
        existing = session.query(User).filter(User.username == ud["username"]).first()
        if existing:
            continue

        user = User(
            username=ud["username"],
            password_hash=hash_password(ud["password"]),
            full_name=ud["full_name"],
            email=ud["email"],
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Assign role
        role = session.query(Role).filter(Role.role_name == ud["role"]).first()
        if role:
            session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
            session.commit()

    print("  ✓ Users seeded (admin/admin123, analyst_joy/analyst123, manager_bob/manager123)")


def seed_branches(session):
    """Seed branches."""
    if session.query(Branch).count() > 0:
        print("  ✓ Branches already seeded, skipping")
        return

    branches = [
        {"branch_code": "BR001", "branch_name": "Main Branch Karachi", "branch_type": "Full Service", "city": "Karachi", "state": "Sindh", "region": "South"},
        {"branch_code": "BR002", "branch_name": "Lahore Central", "branch_type": "Full Service", "city": "Lahore", "state": "Punjab", "region": "Central"},
        {"branch_code": "BR003", "branch_name": "Islamabad Digital Hub", "branch_type": "Digital", "city": "Islamabad", "state": "Federal", "region": "North"},
        {"branch_code": "BR004", "branch_name": "Peshawar Branch", "branch_type": "Full Service", "city": "Peshawar", "state": "KPK", "region": "North"},
        {"branch_code": "BR005", "branch_name": "Multan Branch", "branch_type": "Full Service", "city": "Multan", "state": "Punjab", "region": "Central"},
    ]
    for b in branches:
        session.add(Branch(**b, opened_date=datetime(2020, 1, 1).date()))
    session.commit()
    print("  ✓ Branches seeded")


def seed_customers(session):
    """Seed 20 customers."""
    if session.query(Customer).count() > 0:
        print("  ✓ Customers already seeded, skipping")
        return

    first_names = ["Ahmed", "Sara", "Usman", "Fatima", "Ali", "Ayesha", "Hassan", "Maryam", "Bilal", "Zara",
                   "Omar", "Hira", "Imran", "Nadia", "Tariq", "Sana", "Waseem", "Amna", "Faisal", "Rabia"]
    last_names = ["Khan", "Ahmed", "Ali", "Malik", "Shah", "Butt", "Chaudhry", "Awan", "Qureshi", "Hashmi"]
    segments = ["Retail", "Wealth", "SME", "Corporate"]

    for i, fname in enumerate(first_names):
        customer = Customer(
            first_name=fname,
            last_name=random.choice(last_names),
            date_of_birth=datetime(1975 + random.randint(0, 30), random.randint(1, 12), random.randint(1, 28)).date(),
            address=f"Street {random.randint(1, 50)}, House {random.randint(1, 200)}",
            email=f"{fname.lower()}{i}@example.com",
            phone=f"+92300{random.randint(1000000, 9999999)}",
            segment=random.choice(segments),
            risk_score=random.randint(0, 100),
            kyc_status="Verified",
            status="Active",
        )
        session.add(customer)
    session.commit()
    print("  ✓ Customers seeded")


def seed_accounts(session):
    """Seed 30 accounts across all customers."""
    if session.query(Account).count() > 0:
        print("  ✓ Accounts already seeded, skipping")
        return

    customers = session.query(Customer).all()
    branches = session.query(Branch).all()
    account_types = ["Checking", "Savings", "Business", "Premium Savings"]

    for i, customer in enumerate(customers):
        # Each customer gets 1-2 accounts
        num_accounts = random.randint(1, 2)
        for j in range(num_accounts):
            account = Account(
                account_number=f"PK{random.randint(10, 99)}BANK{str(i * 10 + j + 1001).zfill(8)}",
                customer_id=customer.customer_id,
                branch_id=random.choice(branches).branch_id,
                account_type=random.choice(account_types),
                balance=Decimal(str(round(random.uniform(1000, 500000), 2))),
                currency="PKR",
                status="Active",
                opening_date=datetime(2021 + random.randint(0, 3), random.randint(1, 12), random.randint(1, 28)).date(),
            )
            session.add(account)
    session.commit()
    print("  ✓ Accounts seeded")


def seed_merchants(session):
    """Seed merchant data."""
    if session.query(Merchant).count() > 0:
        print("  ✓ Merchants already seeded, skipping")
        return

    merchants = [
        {"merchant_name": "FoodPanda Pakistan", "category_code": "5411", "location": "Karachi"},
        {"merchant_name": "Daraz.pk", "category_code": "5311", "location": "Lahore"},
        {"merchant_name": "Shell Fuel Station", "category_code": "5541", "location": "Islamabad"},
        {"merchant_name": "Hyperstar", "category_code": "5411", "location": "Karachi"},
        {"merchant_name": "PIA Ticketing", "category_code": "4511", "location": "Karachi"},
        {"merchant_name": "Jazz Telecom", "category_code": "4812", "location": "Lahore"},
        {"merchant_name": "Careem Rides", "category_code": "4121", "location": "Karachi"},
        {"merchant_name": "United Hospital", "category_code": "8011", "location": "Islamabad"},
    ]
    for m in merchants:
        session.add(Merchant(**m))
    session.commit()
    print("  ✓ Merchants seeded")


def seed_cards(session):
    """Seed cards linked to accounts."""
    if session.query(Card).count() > 0:
        print("  ✓ Cards already seeded, skipping")
        return

    customers = session.query(Customer).all()
    for customer in customers[:15]:
        accounts = session.query(Account).filter(Account.customer_id == customer.customer_id).all()
        if not accounts:
            continue
        account = accounts[0]
        card_type = random.choice(["DEBIT", "CREDIT"])
        card = Card(
            customer_id=customer.customer_id,
            linked_account_id=account.account_id,
            card_type=card_type,
            masked_card_number=f"**** **** **** {random.randint(1000, 9999)}",
            expiry_date=datetime(2026 + random.randint(0, 3), random.randint(1, 12), 1).date(),
            status="ACTIVE",
            credit_limit=Decimal(str(random.randint(50000, 500000))) if card_type == "CREDIT" else None,
        )
        session.add(card)
    session.commit()
    print("  ✓ Cards seeded")


def seed_card_transactions(session):
    """Seed card transactions."""
    if session.query(CardTransaction).count() > 0:
        print("  ✓ Card transactions already seeded, skipping")
        return

    cards = session.query(Card).all()
    merchants = session.query(Merchant).all()

    for card in cards:
        num_txns = random.randint(3, 8)
        for _ in range(num_txns):
            txn = CardTransaction(
                card_id=card.card_id,
                merchant_id=random.choice(merchants).merchant_id,
                amount=Decimal(str(round(random.uniform(100, 25000), 2))),
                currency="PKR",
                transaction_date=datetime.now() - timedelta(days=random.randint(1, 90)),
                authorization_status=random.choice(["APPROVED", "APPROVED", "APPROVED", "DECLINED"]),
                settlement_status=random.choice(["SETTLED", "SETTLED", "PENDING"]),
            )
            session.add(txn)
    session.commit()
    print("  ✓ Card transactions seeded")


def seed_external_accounts(session):
    """Seed external accounts."""
    if session.query(ExternalAccount).count() > 0:
        print("  ✓ External accounts already seeded, skipping")
        return

    externals = [
        {"account_holder_name": "Habib Bank Ltd", "bank_name": "HBL", "iban": "PK36HABB0000111222333444"},
        {"account_holder_name": "United Bank Ltd", "bank_name": "UBL", "iban": "PK50UNIL0000222333444555"},
        {"account_holder_name": "MCB Bank", "bank_name": "MCB", "iban": "PK28MUCB0000333444555666"},
        {"account_holder_name": "Allied Bank", "bank_name": "ABL", "iban": "PK70ABPA0000444555666777"},
    ]
    for e in externals:
        session.add(ExternalAccount(**e))
    session.commit()
    print("  ✓ External accounts seeded")


def seed_transactions(session):
    """Seed account transactions."""
    if session.query(Transaction).count() > 0:
        print("  ✓ Transactions already seeded, skipping")
        return

    accounts = session.query(Account).all()
    external_accounts = session.query(ExternalAccount).all()
    cards = session.query(Card).all()

    txn_types = ["DEBIT", "CREDIT", "TRANSFER"]
    descriptions = [
        "Salary Credit", "ATM Withdrawal", "Online Transfer", "Bill Payment",
        "Utility Payment", "Loan Repayment", "POS Purchase", "Dividend Credit",
        "Cash Deposit", "Cheque Deposit", "Standing Order", "Interbank Transfer",
    ]

    for _ in range(100):
        txn_type = random.choice(txn_types)
        sender = random.choice(accounts) if txn_type in ["DEBIT", "TRANSFER"] else None
        receiver = random.choice(accounts) if txn_type in ["CREDIT", "TRANSFER"] else None

        txn = Transaction(
            transaction_date=datetime.now() - timedelta(days=random.randint(1, 120)),
            transaction_type=txn_type,
            amount=Decimal(str(round(random.uniform(500, 100000), 2))),
            description=random.choice(descriptions),
            status=random.choice(["POSTED", "POSTED", "POSTED", "PENDING"]),
            sender_account_id=sender.account_id if sender else None,
            receiver_account_id=receiver.account_id if receiver else None,
            external_account_id=random.choice(external_accounts).external_account_id if random.random() > 0.7 else None,
            card_id=random.choice(cards).card_id if cards and random.random() > 0.8 else None,
        )
        session.add(txn)

    session.commit()
    print("  ✓ Transactions seeded (100 records)")


def run_seed():
    """Execute all seed functions in order."""
    print("\n🌱 Seeding database...\n")
    session = get_db_session()
    try:
        seed_roles(session)
        seed_users(session)
        seed_branches(session)
        seed_customers(session)
        seed_accounts(session)
        seed_merchants(session)
        seed_cards(session)
        seed_card_transactions(session)
        seed_external_accounts(session)
        seed_transactions(session)
        print("\n✅ All seed data created successfully.\n")
    except Exception as e:
        session.rollback()
        print(f"\n❌ Seeding failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
