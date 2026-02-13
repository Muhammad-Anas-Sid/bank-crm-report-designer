"""
Migration runner — applies SQL migration files in order.
Tracks applied migrations in a _migrations table.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.config.settings import Config


def get_engine():
    return create_engine(Config.DATABASE_URL, echo=False)


def ensure_migrations_table(engine):
    """Create the _migrations tracking table if it doesn't exist."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


def get_applied_migrations(engine):
    """Return set of already-applied migration filenames."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT filename FROM _migrations ORDER BY id"))
        return {row[0] for row in result}


def apply_migrations(reset=False):
    """Apply all pending SQL migrations in order."""
    engine = get_engine()

    if reset:
        print("⚠️  RESET MODE — dropping all tables...")
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        print("✓ Schema reset complete.\n")

    ensure_migrations_table(engine)
    applied = get_applied_migrations(engine)

    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    sql_files = sorted([
        f for f in os.listdir(migrations_dir)
        if f.endswith('.sql')
    ])

    if not sql_files:
        print("No migration files found.")
        return

    pending = [f for f in sql_files if f not in applied]

    if not pending:
        print("✓ All migrations already applied.")
        return

    for filename in pending:
        filepath = os.path.join(migrations_dir, filename)
        print(f"Applying migration: {filename}...")

        with open(filepath, 'r') as f:
            sql = f.read()

        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
                conn.execute(
                    text("INSERT INTO _migrations (filename) VALUES (:filename)"),
                    {"filename": filename}
                )
            print(f"  ✓ {filename} applied successfully.")
        except Exception as e:
            print(f"  ✗ Failed to apply {filename}: {e}")
            raise

    print(f"\n✅ {len(pending)} migration(s) applied successfully.")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    apply_migrations(reset=reset)
