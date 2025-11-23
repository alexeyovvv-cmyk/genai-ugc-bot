from __future__ import annotations

import io
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Type
from urllib.parse import urlparse

import requests
from PIL import Image  # type: ignore

from video_editing.render.shotstack import ShotstackError, probe_duration

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".mpg", ".mpeg"}


@dataclass
class MediaMeta:
    asset_type: str
    width: int
    height: int
    duration: float


def _probe_image_meta(path: Path) -> Optional[MediaMeta]:
    try:
        with Image.open(path) as img:
            width, height = img.size
        return MediaMeta(asset_type="image", width=int(width), height=int(height), duration=0.0)
    except (OSError, ValueError):
        return None


def run_ffprobe_meta(
    media_path: Path,
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> MediaMeta:
    image_meta = _probe_image_meta(media_path)
    if image_meta is not None:
        return image_meta

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except FileNotFoundError as exc:
        raise error_cls("Нужен ffprobe, но бинарь не найден в PATH.") from exc
    except subprocess.CalledProcessError as exc:
        image_meta = _probe_image_meta(media_path)
        if image_meta is not None:
            return image_meta
        raise error_cls(f"ffprobe не смог прочитать {media_path}: {exc.stderr.strip()}") from exc

    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, ValueError, IndexError) as exc:
        image_meta = _probe_image_meta(media_path)
        if image_meta is not None:
            return image_meta
        raise error_cls(f"Не удалось распарсить метаданные ffprobe: {result.stdout}") from exc

    try:
        duration = probe_duration(str(media_path))
    except ShotstackError:
        image_meta = _probe_image_meta(media_path)
        if image_meta is not None:
            return image_meta
        raise
    return MediaMeta(asset_type="video", width=width, height=height, duration=duration)


def _content_type_to_media_type(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return None
    content_type = content_type.lower()
    if "image" in content_type:
        return "image"
    if "video" in content_type:
        return "video"
    return None


def sniff_remote_media_type(
    url: str,
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> str:
    parsed = urlparse(url)
    extension = Path(parsed.path).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"

    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        response.raise_for_status()
        media_type = _content_type_to_media_type(response.headers.get("Content-Type"))
        if media_type:
            return media_type
    except requests.RequestException:
        pass

    try:
        with requests.get(url, stream=True, timeout=10) as resp:
            resp.raise_for_status()
            data = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                data.extend(chunk)
                if len(data) >= 131072:
                    break
            if not data:
                return "video"
        try:
            Image.open(io.BytesIO(data))
            return "image"
        except Exception:
            return "video"
    except requests.RequestException:
        return "video"

    return "video"


TARGET_ASPECT = 9 / 16


def decide_fit(width: int, height: int, tolerance: float) -> str:
    if width <= 0 or height <= 0:
        return "cover"
    aspect = width / height
    if abs(aspect - TARGET_ASPECT) <= tolerance:
        return "cover"
    return "contain"
