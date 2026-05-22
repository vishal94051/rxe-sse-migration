import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

def test_postgres():
    print("\n--- Testing Postgres Connection ---")
    try:
        engine = create_engine(os.getenv("POSTGRES_URL"))
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Postgres connected successfully!")
            print(f"   Version: {version[:50]}")
    except Exception as e:
        print(f"❌ Postgres connection failed: {e}")

def test_mongodb():
    print("\n--- Testing MongoDB Connection ---")
    try:
        client = MongoClient(os.getenv("MONGO_URL"))
        # Force connection attempt
        client.admin.command('ping')
        print(f"✅ MongoDB connected successfully!")
        print(f"   Databases: {client.list_database_names()}")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")

if __name__ == "__main__":
    print("Testing database connections...")
    test_postgres()
    test_mongodb()
    print("\nDone!")