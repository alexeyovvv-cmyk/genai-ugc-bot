from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Type
from urllib.parse import urlparse


TARGET_ASPECT = 9 / 16
DEFAULT_FIT_TOLERANCE = 0.02


@dataclass
class MediaMeta:
    width: int
    height: int
    duration: float
    asset_type: str  # "video" or "image"


def run_ffprobe_meta(video_path: Path, *, error_cls: Type[Exception] = RuntimeError) -> MediaMeta:
    """Run ffprobe to extract media metadata."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except FileNotFoundError as exc:
        raise error_cls("Нужен ffprobe, но бинарь не найден в PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise error_cls(f"ffprobe не смог прочитать {video_path}: {exc.stderr.strip()}") from exc

    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
        
        # Try to get duration from stream
        duration_str = stream.get("duration")
        if duration_str:
            duration = float(duration_str)
        else:
            # Fallback to format duration
            duration = _probe_duration(str(video_path), error_cls=error_cls)
    except (KeyError, ValueError, IndexError) as exc:
        raise error_cls(f"Не удалось распарсить метаданные ffprobe: {result.stdout}") from exc

    # Detect if it's an image or video
    asset_type = "video"
    if duration == 0.0 or duration < 0.04:  # Less than 1 frame at 25fps
        asset_type = "image"
        duration = 0.0

    return MediaMeta(width=width, height=height, duration=duration, asset_type=asset_type)


def _probe_duration(src: str, *, error_cls: Type[Exception] = RuntimeError) -> float:
    """Probe duration using ffprobe format duration."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        src,
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise error_cls("ffprobe binary is required but was not found on PATH.") from exc
    if result.returncode != 0:
        raise error_cls(f"ffprobe failed for {src}: {result.stderr.strip()}")
    output = result.stdout.strip()
    try:
        return float(output)
    except ValueError:
        return 0.0


def decide_fit(width: int, height: int, tolerance: float = DEFAULT_FIT_TOLERANCE) -> str:
    """Decide whether to use 'cover' or 'contain' based on aspect ratio."""
    if width <= 0 or height <= 0:
        return "cover"
    aspect = width / height
    if abs(aspect - TARGET_ASPECT) <= tolerance:
        return "cover"
    return "contain"


def sniff_remote_media_type(url: str, *, error_cls: Type[Exception] = RuntimeError) -> str:
    """Sniff media type from URL extension."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    video_extensions = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".m4v"}
    
    for ext in image_extensions:
        if path.endswith(ext):
            return "image"
    
    for ext in video_extensions:
        if path.endswith(ext):
            return "video"
    
    # Default to video if unknown
    return "video"

