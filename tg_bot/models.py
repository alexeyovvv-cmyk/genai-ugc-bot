# models.py — ORM и простые DAO

from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, func, BigInteger

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    credits: Mapped[int] = mapped_column(Integer, default=3)
    selected_voice_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String)  # image|audio|video
    path: Mapped[str] = mapped_column(String)  # локальный путь к файлу (backward compatibility)
    r2_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # R2 object key
    r2_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # cached presigned URL
    r2_url_expires_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)  # URL expiry
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # size in bytes
    version: Mapped[int] = mapped_column(Integer, default=1)  # for avatar versioning
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
    # Новые поля для UGC рекламы
    selected_character_idx: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # индекс выбранного персонажа
    character_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # текст, что должен сказать персонаж
    selected_voice_idx: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # индекс выбранного голоса
    # Дополнительные поля для персонажей
    character_gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # пол персонажа
    character_age: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # возраст персонажа
    character_page: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # текущая страница персонажей
    voice_page: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # текущая страница голосов
    # Character editing fields
    original_character_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # путь к оригинальному изображению персонажа
    edited_character_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # путь к отредактированной версии
    edit_iteration_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # количество итераций редактирования
    # Video format fields
    video_format: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # формат видео ('talking_head', 'character_with_background')
    background_video_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # путь к фоновому видео на R2
    # Last generated video fields (for editing)
    original_video_r2_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # R2 ключ исходного видео (для повторных монтажей)
    original_video_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # URL исходного видео
    last_generated_video_r2_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # R2 ключ последнего сгенерированного видео
    last_generated_video_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # URL последнего видео для быстрого доступа
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    # updated_at можно добавить позже триггером, пока не требуется

class UserActivity(Base):
    __tablename__ = "user_activity"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    last_activity_date: Mapped[str] = mapped_column(String)  # DATE as string YYYY-MM-DD
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class GenerationHistory(Base):
    __tablename__ = "generation_history"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    generation_type: Mapped[str] = mapped_column(String)  # 'video', 'audio', 'avatar_edit'
    r2_video_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    r2_audio_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    r2_image_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    character_gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    character_age: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    text_prompt: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    credits_spent: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
