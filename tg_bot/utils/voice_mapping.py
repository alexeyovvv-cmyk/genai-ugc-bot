"""Voice mapping utilities for automatic voice selection."""
from typing import Optional
from tg_bot.utils.constants import VOICE_MAPPING, DEFAULT_TTS_LANGUAGE, DEFAULT_TTS_EMOTION


def get_voice_for_character(gender: str, age: Optional[str] = None) -> str:
    """
    Get voice ID for character based on gender and age.
    
    Args:
        gender: 'male' or 'female'
        age: 'young', 'elderly' (currently ignored, ready for future expansion)
    
    Returns:
        str: voice_id for MiniMax TTS
        
    Example:
        >>> get_voice_for_character("female")
        "Wise_Woman"
        >>> get_voice_for_character("male", "young")
        "Friendly_Person"
    """
    if gender not in VOICE_MAPPING:
        # Fallback to male voice if gender is unknown
        return VOICE_MAPPING["male"]
    
    return VOICE_MAPPING[gender]


def get_default_language() -> str:
    """Get default language for TTS (ready for future logic)."""
    return DEFAULT_TTS_LANGUAGE


def get_default_emotion() -> str:
    """Get default emotion for TTS (ready for future logic)."""
    return DEFAULT_TTS_EMOTION
