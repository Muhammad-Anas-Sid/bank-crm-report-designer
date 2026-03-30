"""
Backend configuration module.
Loads all settings from environment variables.
"""

import os
from dotenv import load_dotenv

# Load .env from project root
# __file__ = backend/config/settings.py
# dirname 1 = backend/config
# dirname 2 = backend
# dirname 3 = project root
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path)


class Config:
    """Application configuration from environment variables."""

    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "super_secret_bank_key_change_in_production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # PostgreSQL
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "bank_crm")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

    # AI / LLM
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # File paths
    BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
    
    BASE_DIR = BACKEND_DIR # Keeping for legacy compatibility
    REPORTS_DIR = os.path.join(BACKEND_DIR, "generated_reports")
    DATA_INGEST_DIR = os.path.join(PROJECT_ROOT, "data_ingest")
    SCHEMA_METADATA_PATH = os.path.join(PROJECT_ROOT, "config", "schema_metadata.json")
    MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # Valid roles
    VALID_ROLES = ["admin", "analyst", "manager"]
