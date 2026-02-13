-- ============================================================================
-- Bank-Grade AI Report Designer — PostgreSQL Schema
-- Migration: 001_initial_schema.sql
-- ============================================================================
-- Strict rules: All tables have PKs, FKs with referential integrity,
-- indexes on customer_id, account_id, card_id, transaction_date, created_at,
-- snake_case naming, no duplicate entities.
-- ============================================================================

-- ============================================================================
-- SECURITY TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,  -- 'admin', 'analyst', 'manager'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    email VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role_id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    session_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    username VARCHAR(100),
    user_role VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    details TEXT,
    status VARCHAR(20) DEFAULT 'SUCCESS',
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CHAT TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_session_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'New Chat',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id SERIAL PRIMARY KEY,
    chat_session_id INTEGER NOT NULL REFERENCES chat_sessions(chat_session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    message_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- COMMON BANKING TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS branches (
    branch_id SERIAL PRIMARY KEY,
    branch_code VARCHAR(20) UNIQUE NOT NULL,
    branch_name VARCHAR(200) NOT NULL,
    branch_type VARCHAR(50),  -- 'Full Service', 'ATM Only', 'Digital'
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100) DEFAULT 'Pakistan',
    region VARCHAR(50),
    opened_date DATE,
    status VARCHAR(20) DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    position VARCHAR(100),
    branch_id INTEGER REFERENCES branches(branch_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    address TEXT,
    email VARCHAR(200),
    phone VARCHAR(50),
    segment VARCHAR(50) DEFAULT 'Retail',  -- 'Retail', 'Wealth', 'SME', 'Corporate'
    risk_score INTEGER DEFAULT 0,
    kyc_status VARCHAR(20) DEFAULT 'Verified',
    status VARCHAR(20) DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id SERIAL PRIMARY KEY,
    account_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    branch_id INTEGER REFERENCES branches(branch_id) ON DELETE SET NULL,
    account_type VARCHAR(50) NOT NULL,  -- 'Checking', 'Savings', 'Business', 'Premium Savings'
    balance NUMERIC(15, 2) DEFAULT 0.00,
    currency VARCHAR(10) DEFAULT 'PKR',
    status VARCHAR(20) DEFAULT 'Active',
    opening_date DATE,
    last_activity_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CARD MANAGEMENT TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS cards (
    card_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    linked_account_id INTEGER NOT NULL,
    card_type VARCHAR(20) NOT NULL, -- 'DEBIT', 'CREDIT'
    masked_card_number VARCHAR(50) NOT NULL,
    expiry_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'ACTIVE', -- 'ACTIVE', 'BLOCKED', 'EXPIRED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    -- Dependencies on Domain 1
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (linked_account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);
    
CREATE TABLE IF NOT EXISTS card_lifecycle (
    lifecycle_id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL,
    event VARCHAR(50) NOT NULL, -- 'ISSUED', 'ACTIVATED', 'BLOCKED', 'REPLACED'
    event_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (card_id) REFERENCES cards(card_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id SERIAL PRIMARY KEY,
    merchant_name VARCHAR(200) NOT NULL,
    category_code VARCHAR(50),
    location VARCHAR(200),
    status VARCHAR(20) DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS card_transactions (
    card_transaction_id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(card_id) ON DELETE CASCADE,
    merchant_id INTEGER REFERENCES merchants(merchant_id) ON DELETE SET NULL,
    amount NUMERIC(15, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'PKR',
    transaction_date TIMESTAMP NOT NULL,
    authorization_status VARCHAR(20) DEFAULT 'PENDING',
    settlement_status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    FOREIGN KEY (card_id) REFERENCES cards(card_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);

-- ============================================================================
-- TRANSACTION MANAGEMENT TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS external_accounts (
    external_account_id SERIAL PRIMARY KEY,
    account_holder_name VARCHAR(200) NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    iban VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id SERIAL PRIMARY KEY,
    transaction_date TIMESTAMP NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,  -- 'DEBIT', 'CREDIT', 'TRANSFER'
    amount NUMERIC(15, 2) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'PENDING',  -- 'POSTED', 'PENDING', 'FAILED'
    sender_account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL,
    receiver_account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL,
    external_account_id INTEGER REFERENCES external_accounts(external_account_id) ON DELETE SET NULL,
    card_id INTEGER REFERENCES cards(card_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Security indexes
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_created_at ON user_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- Chat indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(chat_session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- Banking indexes
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at);
CREATE INDEX IF NOT EXISTS idx_accounts_customer_id ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_accounts_branch_id ON accounts(branch_id);
CREATE INDEX IF NOT EXISTS idx_accounts_created_at ON accounts(created_at);
CREATE INDEX IF NOT EXISTS idx_branches_created_at ON branches(created_at);

-- Card indexes
CREATE INDEX IF NOT EXISTS idx_cards_customer_id ON cards(customer_id);
CREATE INDEX IF NOT EXISTS idx_cards_linked_account_id ON cards(linked_account_id);
CREATE INDEX IF NOT EXISTS idx_cards_created_at ON cards(created_at);
CREATE INDEX IF NOT EXISTS idx_card_transactions_card_id ON card_transactions(card_id);
CREATE INDEX IF NOT EXISTS idx_card_transactions_merchant_id ON card_transactions(merchant_id);
CREATE INDEX IF NOT EXISTS idx_card_transactions_transaction_date ON card_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_card_transactions_created_at ON card_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_merchants_created_at ON merchants(created_at);

-- Transaction indexes
CREATE INDEX IF NOT EXISTS idx_transactions_sender_account_id ON transactions(sender_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_receiver_account_id ON transactions(receiver_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_card_id ON transactions(card_id);
CREATE INDEX IF NOT EXISTS idx_transactions_transaction_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_external_accounts_created_at ON external_accounts(created_at);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
