import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from backend.config.settings import Config

def create_database():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'bank_crm'")
        exists = cursor.fetchone()
        
        if not exists:
            print("Creating database 'bank_crm'...")
            cursor.execute("CREATE DATABASE bank_crm")
            print("Database 'bank_crm' created successfully.")
        else:
            print("Database 'bank_crm' already exists.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

if __name__ == "__main__":
    create_database()
