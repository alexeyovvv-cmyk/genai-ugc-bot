"""Audio utilities for working with audio files."""
import os
import asyncio
from typing import Optional, List
from pydub import AudioSegment
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)


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


def check_audio_duration_limit(audio_path: str, max_seconds: float = 30.0) -> tuple[bool, float]:
    """
    Check if audio duration is within limit.
    
    Args:
        audio_path: Path to audio file
        max_seconds: Maximum allowed duration in seconds (default 30.0)
        
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


def _concatenate_audio_files_sync(
    audio_paths: List[str], 
    output_path: str,
    pause_duration_ms: int = 130
) -> str:
    """
    Synchronously concatenate multiple audio files with pauses between them.
    
    Args:
        audio_paths: List of paths to audio files (in order)
        output_path: Path to save the concatenated result
        pause_duration_ms: Duration of pause between segments (default 130ms)
    
    Returns:
        Path to concatenated file
    """
    logger.info(f"[AUDIO_CONCAT] Starting concatenation of {len(audio_paths)} audio files")
    logger.info(f"[AUDIO_CONCAT] Pause duration: {pause_duration_ms}ms")
    
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=pause_duration_ms)
    
    for i, path in enumerate(audio_paths):
        logger.info(f"[AUDIO_CONCAT] Loading segment {i+1}/{len(audio_paths)}: {path}")
        audio = AudioSegment.from_file(path)
        duration_sec = len(audio) / 1000.0
        logger.info(f"[AUDIO_CONCAT] Segment {i+1} duration: {duration_sec:.2f}s")
        
        combined += audio
        
        # Add pause between segments (but not after the last one)
        if i < len(audio_paths) - 1:
            logger.info(f"[AUDIO_CONCAT] Adding {pause_duration_ms}ms pause after segment {i+1}")
            combined += silence
    
    total_duration = len(combined) / 1000.0
    logger.info(f"[AUDIO_CONCAT] Total combined duration: {total_duration:.2f}s")
    
    # Save
    logger.info(f"[AUDIO_CONCAT] Exporting to: {output_path}")
    combined.export(output_path, format="mp3")
    
    file_size = os.path.getsize(output_path) / 1024 / 1024  # MB
    logger.info(f"[AUDIO_CONCAT] Export completed: {file_size:.2f}MB")
    
    return output_path


async def concatenate_audio_files(
    audio_paths: List[str], 
    output_path: str,
    pause_duration_ms: int = 130
) -> str:
    """
    Concatenate multiple audio files with pauses between them.
    
    Args:
        audio_paths: List of paths to audio files (in order)
        output_path: Path to save the concatenated result
        pause_duration_ms: Duration of pause between segments (default 130ms)
    
    Returns:
        Path to concatenated file
    """
    return await asyncio.to_thread(
        _concatenate_audio_files_sync,
        audio_paths,
        output_path,
        pause_duration_ms
    )

