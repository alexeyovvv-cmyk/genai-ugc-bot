# db.py — инициализация БД и сессии SQLAlchemy (PostgreSQL/SQLite)
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use PostgreSQL on Railway, SQLite locally
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Railway PostgreSQL
    # Hide password in logs
    safe_url = DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL
    print(f"✅ Using PostgreSQL database: ...@{safe_url}")
    engine = create_engine(DATABASE_URL, echo=False, future=True)
else:
    # Local SQLite fallback
    print("⚠️  Using local SQLite database (genai.db)")
    engine = create_engine("sqlite:///genai.db", echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
