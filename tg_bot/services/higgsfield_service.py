# higgsfield_service.py — обёртки под Higgsfield API
# ВНИМАНИЕ: специфика эндпоинтов может отличаться — подставьте реальные.
import os, httpx, uuid, time, pathlib
from typing import Optional

HF_KEY = os.environ.get("HIGGSFIELD_API_KEY", "")
VIDEO_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "video"
IMG_DIR   = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "start_frames"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.higgsfield.ai/v1"

async def edit_image(seed_image_path: str, prompt: str) -> str:
    """
    Если у Higgsfield есть image-edit/text-to-image — используем его.
    Возвращает путь к новому изображению.
    """
    return "data/fake_image.jpg"

async def create_talking_video(image_path: str, audio_path: Optional[str], text: Optional[str], voice_id: str) -> str:
    """
    Создаёт говорящий ролик: image + либо готовое audio, либо text+voice (если Higgsfield сам озвучивает).
    Возвращает локальный путь к .mp4
    """
    return "data/fake_video.mp4"
