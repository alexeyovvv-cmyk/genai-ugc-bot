"""Video utilities for working with video files."""
import os
from typing import Optional, Tuple


def get_video_duration(video_path: str) -> Optional[float]:
    """
    Get duration of video file in seconds.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Duration in seconds, or None if error
    """
    try:
        # Try using mutagen for video files
        try:
            from mutagen.mp4 import MP4
            from mutagen import File
            
            ext = os.path.splitext(video_path)[1].lower()
            
            if ext in ['.mp4', '.m4v']:
                video = MP4(video_path)
            else:
                # Try generic mutagen
                video = File(video_path)
            
            if video and video.info:
                return float(video.info.length)
        except ImportError:
            # Fallback to ffprobe if available
            try:
                import subprocess
                import json
                
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    video_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    duration = data.get('format', {}).get('duration')
                    if duration:
                        return float(duration)
            except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                pass
            
            # Last fallback: try moviepy
            try:
                from moviepy.editor import VideoFileClip
                with VideoFileClip(video_path) as clip:
                    return float(clip.duration)
            except ImportError:
                pass
                
    except Exception as e:
        from tg_bot.utils.logger import setup_logger
        logger = setup_logger(__name__)
        logger.error(f"Error getting video duration: {e}")
        return None
    
    return None


def check_video_duration_limit(video_path: str, max_seconds: float = 15.0) -> Tuple[bool, float]:
    """
    Check if video duration is within limit.
    
    Args:
        video_path: Path to video file
        max_seconds: Maximum allowed duration in seconds
        
    Returns:
        Tuple of (is_valid, duration_seconds)
        - is_valid: True if duration <= max_seconds, False otherwise
        - duration_seconds: Actual duration in seconds (or 0 if error)
    """
    duration = get_video_duration(video_path)
    
    if duration is None:
        # If we can't determine duration, assume it's invalid
        return False, 0.0
    
    is_valid = duration <= max_seconds
    return is_valid, duration


