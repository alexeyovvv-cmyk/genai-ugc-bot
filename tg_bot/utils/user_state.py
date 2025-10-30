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


# Character editing state helpers
def set_original_character_path(tg_id: int, path: Optional[str]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.original_character_path = path
        db.commit()


def get_original_character_path(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.original_character_path if state else None


def set_edited_character_path(tg_id: int, path: Optional[str]) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.edited_character_path = path
        db.commit()


def get_edited_character_path(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.edited_character_path if state else None


def increment_edit_iteration(tg_id: int) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.edit_iteration_count = (state.edit_iteration_count or 0) + 1
        db.commit()


def clear_edit_session(tg_id: int) -> None:
    """Clean up temporary edit data"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.original_character_path = None
        state.edited_character_path = None
        state.edit_iteration_count = 0
        db.commit()


# Character selection state helpers
def set_character_gender(tg_id: int, gender: str) -> None:
    """Set character gender for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.character_gender = gender
        db.commit()


def get_character_gender(tg_id: int) -> Optional[str]:
    """Get character gender for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.character_gender if state else None


def set_character_age(tg_id: int, age: str) -> None:
    """Set character age for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.character_age = age
        db.commit()


def get_character_age(tg_id: int) -> Optional[str]:
    """Get character age for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.character_age if state else None


def set_character_page(tg_id: int, page: int) -> None:
    """Set character page for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.character_page = page
        db.commit()


def get_character_page(tg_id: int) -> int:
    """Get character page for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return 0
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.character_page if state and state.character_page is not None else 0


def set_voice_page(tg_id: int, page: int) -> None:
    """Set voice page for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.voice_page = page
        db.commit()


def get_voice_page(tg_id: int) -> int:
    """Get voice page for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return 0
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.voice_page if state and state.voice_page is not None else 0


# Video format state helpers
def set_video_format(tg_id: int, format: Optional[str]) -> None:
    """Set video format for user ('talking_head' or 'character_with_background')"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.video_format = format
        db.commit()


def get_video_format(tg_id: int) -> Optional[str]:
    """Get video format for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.video_format if state else None


def set_background_video_path(tg_id: int, path: Optional[str]) -> None:
    """Set background video path for user (R2 key)"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.background_video_path = path
        db.commit()


def get_background_video_path(tg_id: int) -> Optional[str]:
    """Get background video path for user (R2 key)"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        return state.background_video_path if state else None


# Last generated video state helpers (for video editing)
def set_original_video(tg_id: int, r2_key: Optional[str], url: Optional[str] = None) -> None:
    """Set original video R2 key and URL for user (for re-editing)"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.original_video_r2_key = r2_key
        state.original_video_url = url
        db.commit()


def get_original_video(tg_id: int) -> Optional[dict]:
    """Get original video data for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        if not state:
            return None
        return {
            'r2_key': state.original_video_r2_key,
            'url': state.original_video_url
        }


def set_last_generated_video(tg_id: int, r2_key: Optional[str], url: Optional[str] = None) -> None:
    """Set last generated video R2 key and URL for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.last_generated_video_r2_key = r2_key
        state.last_generated_video_url = url
        db.commit()


def get_last_generated_video(tg_id: int) -> Optional[dict]:
    """Get last generated video data for user"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        if not state:
            return None
        return {
            'r2_key': state.last_generated_video_r2_key,
            'url': state.last_generated_video_url
        }


def clear_all_video_data(tg_id: int) -> None:
    """Clear all video data for user (original and last generated) including overlay cache"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        state.original_video_r2_key = None
        state.original_video_url = None
        state.last_generated_video_r2_key = None
        state.last_generated_video_url = None
        db.commit()
    
    # Clear overlay cache
    clear_cached_overlays(tg_id)


# Overlay cache helpers
def set_cached_overlay_urls(tg_id: int, overlay_urls: dict, r2_keys: dict) -> None:
    """
    Cache overlay URLs for current editing session.
    
    Args:
        tg_id: Telegram user ID
        overlay_urls: Dict with 'circle' and/or 'rect' keys mapping to Shotstack URLs
        r2_keys: Dict with 'circle' and/or 'rect' keys mapping to R2 keys
    """
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = _get_or_create_state(db, user.id)
        
        if 'circle' in overlay_urls:
            state.cached_overlay_circle_url = overlay_urls['circle']
            state.cached_overlay_circle_r2_key = r2_keys.get('circle')
        if 'rect' in overlay_urls:
            state.cached_overlay_rect_url = overlay_urls['rect']
            state.cached_overlay_rect_r2_key = r2_keys.get('rect')
        
        from datetime import datetime
        state.overlay_cache_created_at = datetime.utcnow()
        db.commit()


def get_cached_overlay_urls(tg_id: int) -> Optional[dict]:
    """
    Get cached overlay URLs for current editing session.
    
    Returns:
        Dict with 'circle' and/or 'rect' keys, or None if no cache
    """
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        if not state:
            return None
        
        result = {}
        if state.cached_overlay_circle_url:
            result['circle'] = state.cached_overlay_circle_url
        if state.cached_overlay_rect_url:
            result['rect'] = state.cached_overlay_rect_url
        
        return result if result else None


def clear_cached_overlays(tg_id: int) -> None:
    """Clear overlay cache and delete files from R2."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return
        state = db.scalar(select(UserState).where(UserState.user_id == user.id))
        if not state:
            return
        
        # Delete from R2
        from tg_bot.services.r2_service import delete_file
        if state.cached_overlay_circle_r2_key:
            delete_file(state.cached_overlay_circle_r2_key)
        if state.cached_overlay_rect_r2_key:
            delete_file(state.cached_overlay_rect_r2_key)
        
        # Clear from DB
        state.cached_overlay_circle_url = None
        state.cached_overlay_rect_url = None
        state.cached_overlay_circle_r2_key = None
        state.cached_overlay_rect_r2_key = None
        state.overlay_cache_created_at = None
        db.commit()

