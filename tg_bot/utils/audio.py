"""Audio utilities for working with audio files."""
import os
from typing import Optional


def get_audio_duration(audio_path: str) -> Optional[float]:
    """
    Get duration of audio file in seconds.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Duration in seconds, or None if error
    """
    try:
        # Try using mutagen (lightweight, commonly available)
        try:
            from mutagen.mp3 import MP3
            from mutagen.wave import WAVE
            from mutagen.oggvorbis import OggVorbis
            from mutagen.flac import FLAC
            
            ext = os.path.splitext(audio_path)[1].lower()
            
            if ext == '.mp3':
                audio = MP3(audio_path)
            elif ext == '.wav':
                audio = WAVE(audio_path)
            elif ext == '.ogg':
                audio = OggVorbis(audio_path)
            elif ext == '.flac':
                audio = FLAC(audio_path)
            else:
                # Try generic mutagen
                from mutagen import File
                audio = File(audio_path)
            
            if audio and audio.info:
                return float(audio.info.length)
        except ImportError:
            # Fallback to pydub if mutagen not available
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # Convert ms to seconds
            
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return None


def check_audio_duration_limit(audio_path: str, max_seconds: float = 15.0) -> tuple[bool, float]:
    """
    Check if audio duration is within limit.
    
    Args:
        audio_path: Path to audio file
        max_seconds: Maximum allowed duration in seconds
        
    Returns:
        Tuple of (is_valid, duration_seconds)
        - is_valid: True if duration <= max_seconds, False otherwise
        - duration_seconds: Actual duration in seconds (or 0 if error)
    """
    duration = get_audio_duration(audio_path)
    
    if duration is None:
        # If we can't determine duration, assume it's invalid
        return False, 0.0
    
    is_valid = duration <= max_seconds
    return is_valid, duration

