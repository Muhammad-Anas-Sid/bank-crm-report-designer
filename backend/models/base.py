"""
SQLAlchemy base configuration — engine, session, and declarative base.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config.settings import Config

engine = create_engine(Config.DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db_session():
    """Create a new database session. Caller must close it."""
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise


def get_db_engine():
    """Return the shared SQLAlchemy engine."""
    return engine
