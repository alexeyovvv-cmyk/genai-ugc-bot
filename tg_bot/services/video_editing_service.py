"""
Сервис для автоматического монтажа видео через Shotstack API.

Предоставляет упрощенные обертки над video_editing/autopipeline.py
для интеграции с телеграм-ботом.
"""
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

from ..config import r2_client, BUCKET_NAME
from ..utils.r2_utils import upload_file_to_r2, get_presigned_url

logger = logging.getLogger(__name__)

# Путь к autopipeline.py
VIDEO_EDITING_DIR = Path(__file__).parent.parent.parent / "video_editing"
AUTOPIPELINE_SCRIPT = VIDEO_EDITING_DIR / "autopipeline.py"


class VideoEditingError(Exception):
    """Ошибка при монтаже видео"""
    pass


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
        head_url = get_presigned_url(video_r2_key, expiration=3600)
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
            ]
            
            logger.info(f"Running autopipeline: {' '.join(cmd)}")
            
            # Установить переменные окружения
            env = os.environ.copy()
            env["SHOTSTACK_API_KEY"] = api_key
            env["SHOTSTACK_STAGE"] = stage
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(VIDEO_EDITING_DIR)
            )
            
            if result.returncode != 0:
                logger.error(f"Autopipeline failed: {result.stderr}")
                raise VideoEditingError(f"Autopipeline failed: {result.stderr[:200]}")
            
            logger.info(f"Autopipeline output: {result.stdout}")
            
            # 4. Найти результирующий файл
            # autopipeline сохраняет результаты как basic_final.mp4 (или аналогично)
            result_files = list(output_dir.glob("*.mp4"))
            if not result_files:
                # Попробуем найти в build/
                build_dir = VIDEO_EDITING_DIR / "build"
                result_files = list(build_dir.glob("**/basic_final.mp4"))
            
            if not result_files:
                raise VideoEditingError("No output video found after autopipeline")
            
            result_file = result_files[0]
            logger.info(f"Found result file: {result_file}")
            
            # 5. Загрузить результат в R2
            timestamp = int(time.time())
            result_r2_key = f"users/{user_id}/edited_videos/subtitled_{timestamp}.mp4"
            
            upload_success = upload_file_to_r2(str(result_file), result_r2_key)
            if not upload_success:
                raise VideoEditingError("Failed to upload result to R2")
            
            # 6. Получить presigned URL для результата
            result_url = get_presigned_url(result_r2_key, expiration=86400)  # 24 часа
            
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
        head_url = get_presigned_url(head_r2_key, expiration=3600)
        bg_url = get_presigned_url(background_r2_key, expiration=3600)
        
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
            ]
            
            logger.info(f"Running autopipeline: {' '.join(cmd)}")
            
            env = os.environ.copy()
            env["SHOTSTACK_API_KEY"] = api_key
            env["SHOTSTACK_STAGE"] = stage
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(VIDEO_EDITING_DIR)
            )
            
            if result.returncode != 0:
                logger.error(f"Autopipeline failed: {result.stderr}")
                raise VideoEditingError(f"Autopipeline failed: {result.stderr[:200]}")
            
            logger.info(f"Autopipeline output: {result.stdout}")
            
            # 4. Найти результирующий файл
            result_files = list(output_dir.glob("*.mp4"))
            if not result_files:
                build_dir = VIDEO_EDITING_DIR / "build"
                result_files = list(build_dir.glob("**/mix_basic_circle_final.mp4"))
            
            if not result_files:
                raise VideoEditingError("No output video found after autopipeline")
            
            result_file = result_files[0]
            logger.info(f"Found result file: {result_file}")
            
            # 5. Загрузить результат в R2
            timestamp = int(time.time())
            result_r2_key = f"users/{user_id}/edited_videos/composite_{timestamp}.mp4"
            
            upload_success = upload_file_to_r2(str(result_file), result_r2_key)
            if not upload_success:
                raise VideoEditingError("Failed to upload result to R2")
            
            # 6. Получить presigned URL
            result_url = get_presigned_url(result_r2_key, expiration=86400)
            
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

