"""
Сервис для автоматического монтажа видео через Shotstack API.

Предоставляет упрощенные обертки над video_editing/autopipeline.py
для интеграции с телеграм-ботом.
"""
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from .r2_service import upload_file, get_presigned_url

logger = logging.getLogger(__name__)

# Путь к autopipeline.py
VIDEO_EDITING_DIR = Path(__file__).parent.parent.parent / "video_editing"
AUTOPIPELINE_SCRIPT = VIDEO_EDITING_DIR / "autopipeline.py"


class VideoEditingError(Exception):
    """Ошибка при монтаже видео"""
    pass


def extract_video_url_from_output(stdout: str) -> Optional[str]:
    """
    Извлечь URL видео из вывода autopipeline.
    
    Autopipeline выводит в конце:
    Результаты:
    - template_name: https://shotstack.io/.../video.mp4
    """
    # Ищем URL в формате: "- <name>: <url>"
    # Используем .+ вместо \w+ чтобы захватить точки и подчеркивания в названии
    pattern = r'- .+:\s+(https?://[^\s]+\.mp4)'
    match = re.search(pattern, stdout)
    if match:
        return match.group(1)
    return None


def download_video_from_url(url: str, local_path: str) -> bool:
    """
    Скачать видео по URL.
    
    Args:
        url: URL видео
        local_path: путь для сохранения
    
    Returns:
        bool: успешность скачивания
    """
    try:
        logger.info(f"Downloading video from {url}")
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Video downloaded successfully to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download video: {e}")
        return False


async def add_subtitles_to_video(
    video_r2_key: str,
    text: str,
    user_id: int
) -> Dict[str, str]:
    """
    Наложить субтитры на видео (формат talking_head).
    
    Args:
        video_r2_key: R2 ключ исходного видео
        text: Транскрипт для субтитров
        user_id: ID пользователя (для именования результата)
    
    Returns:
        Dict с ключами:
            - r2_key: ключ результата в R2
            - url: presigned URL для скачивания
    
    Raises:
        VideoEditingError: при ошибке монтажа
    """
    try:
        logger.info(f"Starting subtitle overlay for user {user_id}, video {video_r2_key}")
        
        # 1. Получить presigned URL для исходного видео
        head_url = get_presigned_url(video_r2_key, expiry_hours=1)
        if not head_url:
            raise VideoEditingError(f"Failed to get presigned URL for {video_r2_key}")
        
        # 2. Проверить наличие Shotstack credentials
        api_key = os.getenv("SHOTSTACK_API_KEY")
        if not api_key:
            raise VideoEditingError("SHOTSTACK_API_KEY not configured")
        
        stage = os.getenv("SHOTSTACK_STAGE", "v1")
        
        # 3. Запустить autopipeline с параметрами для субтитров
        # Используем только talking_head (no overlay, just subtitles on original video)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            cmd = [
                sys.executable,
                str(AUTOPIPELINE_SCRIPT),
                "--background-url", head_url,  # используем head как фон для простоты
                "--head-url", head_url,
                "--templates", "basic",  # базовый шаблон без overlay
                "--subtitles-enabled", "auto",
                "--transcript", text,
                "--output-dir", str(output_dir),
                "--rembg-model", "u2net_human_seg",  # быстрая модель для людей
            ]
            
            logger.info(f"Running autopipeline: {' '.join(cmd)}")
            
            # Установить переменные окружения
            env = os.environ.copy()
            env["SHOTSTACK_API_KEY"] = api_key
            env["SHOTSTACK_STAGE"] = stage
            # Оптимизации скорости
            env["SHOTSTACK_POLL_SECONDS"] = "3"  # чаще проверять статус рендера
            env["U2NET_HOME"] = "/tmp/.u2net"  # кэш rembg моделей
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(VIDEO_EDITING_DIR)
            )
            
            if result.returncode != 0:
                logger.error(f"Autopipeline failed with code {result.returncode}")
                logger.error(f"STDERR: {result.stderr}")
                logger.error(f"STDOUT: {result.stdout}")
                raise VideoEditingError(f"Autopipeline failed: {result.stderr[:200]}")
            
            logger.info(f"Autopipeline completed successfully")
            logger.info(f"STDOUT: {result.stdout}")
            if result.stderr:
                logger.info(f"STDERR: {result.stderr}")
            
            # 4. Извлечь URL видео из вывода
            video_url = extract_video_url_from_output(result.stdout)
            if not video_url:
                logger.error(f"Failed to extract video URL from output")
                logger.error(f"Full stdout: {result.stdout}")
                raise VideoEditingError("Failed to extract video URL from autopipeline output")
            
            logger.info(f"Extracted video URL: {video_url}")
            
            # 5. Скачать видео
            result_file = Path(tmpdir) / f"subtitled_{user_id}_{int(time.time())}.mp4"
            if not download_video_from_url(video_url, str(result_file)):
                raise VideoEditingError("Failed to download rendered video from Shotstack")
            
            logger.info(f"Downloaded video to: {result_file}")
            
            # 5. Загрузить результат в R2
            timestamp = int(time.time())
            result_r2_key = f"users/{user_id}/edited_videos/subtitled_{timestamp}.mp4"
            
            upload_success = upload_file(str(result_file), result_r2_key)
            if not upload_success:
                raise VideoEditingError("Failed to upload result to R2")
            
            # 6. Получить presigned URL для результата
            result_url = get_presigned_url(result_r2_key, expiry_hours=24)  # 24 часа
            
            logger.info(f"Successfully created subtitled video: {result_r2_key}")
            
            return {
                "r2_key": result_r2_key,
                "url": result_url or ""
            }
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess error in add_subtitles_to_video: {e}")
        raise VideoEditingError(f"Video processing failed: {e}")
    except Exception as e:
        logger.error(f"Error in add_subtitles_to_video: {e}", exc_info=True)
        raise VideoEditingError(f"Video editing failed: {e}")


async def composite_head_with_background(
    head_r2_key: str,
    background_r2_key: str,
    text: str,
    user_id: int
) -> Dict[str, str]:
    """
    Смонтировать видео с говорящей головой на фоне.
    
    Args:
        head_r2_key: R2 ключ видео с головой
        background_r2_key: R2 ключ фонового видео
        text: Транскрипт для субтитров
        user_id: ID пользователя
    
    Returns:
        Dict с ключами:
            - r2_key: ключ результата в R2
            - url: presigned URL для скачивания
    
    Raises:
        VideoEditingError: при ошибке монтажа
    """
    try:
        logger.info(f"Starting composite for user {user_id}, head={head_r2_key}, bg={background_r2_key}")
        
        # 1. Получить presigned URLs
        head_url = get_presigned_url(head_r2_key, expiry_hours=1)
        bg_url = get_presigned_url(background_r2_key, expiry_hours=1)
        
        if not head_url or not bg_url:
            raise VideoEditingError("Failed to get presigned URLs")
        
        # 2. Проверить Shotstack credentials
        api_key = os.getenv("SHOTSTACK_API_KEY")
        if not api_key:
            raise VideoEditingError("SHOTSTACK_API_KEY not configured")
        
        stage = os.getenv("SHOTSTACK_STAGE", "v1")
        
        # 3. Запустить autopipeline с mix_basic_circle композицией
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            cmd = [
                sys.executable,
                str(AUTOPIPELINE_SCRIPT),
                "--background-url", bg_url,
                "--head-url", head_url,
                "--templates", "mix_basic_circle",  # используем mix_basic_circle шаблон
                "--subtitles-enabled", "auto",
                "--transcript", text,
                "--output-dir", str(output_dir),
                "--rembg-model", "u2net_human_seg",  # быстрая модель для людей
            ]
            
            logger.info(f"Running autopipeline: {' '.join(cmd)}")
            
            env = os.environ.copy()
            env["SHOTSTACK_API_KEY"] = api_key
            env["SHOTSTACK_STAGE"] = stage
            # Оптимизации скорости
            env["SHOTSTACK_POLL_SECONDS"] = "3"  # чаще проверять статус рендера
            env["U2NET_HOME"] = "/tmp/.u2net"  # кэш rembg моделей
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(VIDEO_EDITING_DIR)
            )
            
            if result.returncode != 0:
                logger.error(f"Autopipeline failed with code {result.returncode}")
                logger.error(f"STDERR: {result.stderr}")
                logger.error(f"STDOUT: {result.stdout}")
                raise VideoEditingError(f"Autopipeline failed: {result.stderr[:200]}")
            
            logger.info(f"Autopipeline completed successfully")
            logger.info(f"STDOUT: {result.stdout}")
            if result.stderr:
                logger.info(f"STDERR: {result.stderr}")
            
            # 4. Извлечь URL видео из вывода
            video_url = extract_video_url_from_output(result.stdout)
            if not video_url:
                logger.error(f"Failed to extract video URL from output")
                logger.error(f"Full stdout: {result.stdout}")
                raise VideoEditingError("Failed to extract video URL from autopipeline output")
            
            logger.info(f"Extracted video URL: {video_url}")
            
            # 5. Скачать видео
            result_file = Path(tmpdir) / f"composite_{user_id}_{int(time.time())}.mp4"
            if not download_video_from_url(video_url, str(result_file)):
                raise VideoEditingError("Failed to download rendered video from Shotstack")
            
            logger.info(f"Downloaded video to: {result_file}")
            
            # 5. Загрузить результат в R2
            timestamp = int(time.time())
            result_r2_key = f"users/{user_id}/edited_videos/composite_{timestamp}.mp4"
            
            upload_success = upload_file(str(result_file), result_r2_key)
            if not upload_success:
                raise VideoEditingError("Failed to upload result to R2")
            
            # 6. Получить presigned URL
            result_url = get_presigned_url(result_r2_key, expiry_hours=24)
            
            logger.info(f"Successfully created composite video: {result_r2_key}")
            
            return {
                "r2_key": result_r2_key,
                "url": result_url or ""
            }
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess error in composite_head_with_background: {e}")
        raise VideoEditingError(f"Video processing failed: {e}")
    except Exception as e:
        logger.error(f"Error in composite_head_with_background: {e}", exc_info=True)
        raise VideoEditingError(f"Video editing failed: {e}")

