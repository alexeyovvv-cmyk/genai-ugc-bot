"""Emotion mapping and normalization utilities for TTS."""
from tg_bot.utils.constants import DEFAULT_TTS_EMOTION
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

# Supported emotions for MiniMax TTS
SUPPORTED_EMOTIONS = [
    "happy",
    "sad", 
    "angry",
    "fearful",
    "disgusted",
    "surprised",
    "neutral"
]


def normalize_emotion(tag: str) -> str:
    """
    Normalize and validate emotion tag.
    
    Args:
        tag: Emotion tag from OpenAI response
        
    Returns:
        Valid emotion for MiniMax TTS (from SUPPORTED_EMOTIONS)
    """
    tag_lower = tag.lower().strip()
    
    if tag_lower in SUPPORTED_EMOTIONS:
        logger.info(f"[EMOTION] Normalized tag '{tag}' -> '{tag_lower}'")
        return tag_lower
    else:
        logger.warning(f"[EMOTION] Unknown emotion tag '{tag}', using default '{DEFAULT_TTS_EMOTION}'")
        return DEFAULT_TTS_EMOTION


