from typing import Optional

from sqlalchemy import select

from tg_bot.db import SessionLocal
from tg_bot.models import User, UserState


def _get_or_create_state(db, user_id: int) -> UserState:
    state = db.scalar(select(UserState).where(UserState.user_id == user_id))
    if state:
        return state
    state = UserState(user_id=user_id)
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def set_selected_frame(tg_id: int, frame_path: Optional[str]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.selected_frame_path = frame_path
        db.commit()


def get_selected_frame(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.selected_frame_path if state else None


def set_last_audio(tg_id: int, audio_path: Optional[str]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.last_audio_path = audio_path
        db.commit()


def get_last_audio(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.last_audio_path if state else None


def set_selected_voice(tg_id: int, voice_id: Optional[str]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        user.selected_voice_id = voice_id
        db.commit()


def get_selected_voice(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        return user.selected_voice_id if user else None


# UGC Creation state helpers
def set_selected_character(tg_id: int, character_idx: Optional[int]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.selected_character_idx = character_idx
        db.commit()


def get_selected_character(tg_id: int) -> Optional[int]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.selected_character_idx if state else None


def set_character_text(tg_id: int, text: Optional[str]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.character_text = text
        db.commit()


def get_character_text(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.character_text if state else None




