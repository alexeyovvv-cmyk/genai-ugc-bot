# db.py — инициализация БД и сессии SQLAlchemy (PostgreSQL/SQLite)
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use PostgreSQL on Railway, SQLite locally
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Railway PostgreSQL
    engine = create_engine(DATABASE_URL, echo=False, future=True)
else:
    # Local SQLite fallback
    engine = create_engine("sqlite:///genai.db", echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
