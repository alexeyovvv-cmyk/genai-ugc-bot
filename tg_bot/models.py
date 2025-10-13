# models.py — ORM и простые DAO

from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, func

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(unique=True, index=True)
    credits: Mapped[int] = mapped_column(Integer, default=10)
    selected_voice_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String)  # image|audio|video
    path: Mapped[str] = mapped_column(String)  # локальный путь к файлу
    meta_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class CreditLog(Base):
    __tablename__ = "credit_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    delta: Mapped[int] = mapped_column(Integer)  # +начисление / -списание
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class UserState(Base):
    __tablename__ = "user_state"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    selected_frame_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_audio_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    # updated_at можно добавить позже триггером, пока не требуется
