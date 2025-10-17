# db.py — инициализация БД и сессии SQLAlchemy (PostgreSQL/SQLite)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tg_bot.config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith("sqlite:")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
