"""
Сервис для автоматического монтажа видео через Shotstack API.

Предоставляет упрощенные обертки над video_editing/autopipeline.py
для интеграции с телеграм-ботом.
"""
import copy
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from .r2_service import upload_file, get_presigned_url, download_file
from ..utils.timing import log_timing, format_size
from tg_bot.models import RenderSession
from tg_bot.utils.render_session import (
    create_render_session,
    update_render_session_result,
    get_latest_render_session,
    DEFAULT_CIRCLE_SETTINGS,
)

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = ["mix_basic_circle"]
DEFAULT_SUBTITLE_THEME = "light"
DEFAULT_SCENARIO = "composite"
SHOTSTACK_POLL_SECONDS = os.getenv("SHOTSTACK_POLL_SECONDS", "3")
U2NET_CACHE_DIR = os.getenv("U2NET_HOME", "/tmp/.u2net")


def _ensure_templates_list(templates: Optional[Sequence[str]]) -> Sequence[str]:
    items = [item.strip() for item in (templates or []) if item]
    return items or list(DEFAULT_TEMPLATES)


def _normalize_subtitle_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = {
        "mode": "auto",
        "theme": DEFAULT_SUBTITLE_THEME,
        "transcript": None,
        "file_r2_key": None,
    }
    if settings:
        for key, value in settings.items():
            base[key] = value
    return base


def _normalize_clip_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = {
        "enabled": False,
        "url": None,
        "length": 2.5,
        "templates": [],
    }
    if settings:
        for key, value in settings.items():
            base[key] = value
    return base


def _normalize_circle_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    circle = copy.deepcopy(DEFAULT_CIRCLE_SETTINGS)
    if settings:
        for key, value in settings.items():
            circle[key] = value
    if "auto_center" not in circle:
        circle["auto_center"] = True
    return circle


def _download_manual_subtitles(subtitle_settings: Dict[str, Any], tmpdir: Path) -> Optional[str]:
    if subtitle_settings.get("mode") != "manual":
        return None
    local_path = subtitle_settings.get("local_path")
    if local_path:
        return local_path
    r2_key = subtitle_settings.get("file_r2_key")
    if not r2_key:
        raise VideoEditingError("Manual subtitles mode selected but file_r2_key is missing.")
    dst = Path(tmpdir) / "manual_subtitles.json"
    if not download_file(r2_key, str(dst)):
        raise VideoEditingError("Failed to download subtitles JSON from R2.")
    return str(dst)


def _build_autopipeline_command(
    *,
    background_url: str,
    head_url: str,
    templates: Sequence[str],
    subtitle_settings: Dict[str, Any],
    intro_settings: Dict[str, Any],
    outro_settings: Dict[str, Any],
    circle_settings: Dict[str, Any],
    output_dir: Path,
    user_id: int,
    manual_subtitles_path: Optional[str],
) -> List[str]:
    cmd: List[str] = [
        sys.executable,
        str(AUTOPIPELINE_SCRIPT),
        "--background-url",
        background_url,
        "--head-url",
        head_url,
        "--templates",
        ",".join(templates),
        "--output-dir",
        str(output_dir),
        "--user-id",
        str(user_id),
    ]

    mode = (subtitle_settings.get("mode") or "auto").lower()
    cmd += ["--subtitles-enabled", mode]
    if mode == "auto":
        transcript = subtitle_settings.get("transcript")
        if transcript:
            cmd += ["--transcript", transcript]
    elif mode == "manual":
        if not manual_subtitles_path:
            raise VideoEditingError("Manual subtitles mode requires a downloaded JSON file.")
        cmd += ["--subtitles", manual_subtitles_path]
    theme = subtitle_settings.get("theme")
    if theme:
        cmd += ["--subtitle-theme", theme]

    if intro_settings.get("enabled") and intro_settings.get("url"):
        intro_templates = _ensure_templates_list(intro_settings.get("templates") or templates)
        cmd += [
            "--intro-url",
            intro_settings["url"],
            "--intro-length",
            str(intro_settings.get("length", 2.5)),
            "--intro-templates",
            ",".join(intro_templates),
        ]
    if outro_settings.get("enabled") and outro_settings.get("url"):
        outro_templates = _ensure_templates_list(outro_settings.get("templates") or templates)
        cmd += [
            "--outro-url",
            outro_settings["url"],
            "--outro-length",
            str(outro_settings.get("length", 2.5)),
            "--outro-templates",
            ",".join(outro_templates),
        ]

    cmd += [
        "--circle-radius",
        str(circle_settings.get("radius", DEFAULT_CIRCLE_SETTINGS["radius"])),
        "--circle-center-x",
        str(circle_settings.get("center_x", DEFAULT_CIRCLE_SETTINGS["center_x"])),
        "--circle-center-y",
        str(circle_settings.get("center_y", DEFAULT_CIRCLE_SETTINGS["center_y"])),
    ]
    if not circle_settings.get("auto_center", True):
        cmd.append("--no-circle-auto-center")

    return cmd


def _build_autopipeline_env() -> Dict[str, str]:
    env = os.environ.copy()
    api_key = env.get("SHOTSTACK_API_KEY")
    if not api_key:
        raise VideoEditingError("SHOTSTACK_API_KEY not configured")
    env["SHOTSTACK_STAGE"] = env.get("SHOTSTACK_STAGE", "v1")
    env["SHOTSTACK_POLL_SECONDS"] = SHOTSTACK_POLL_SECONDS
    env["U2NET_HOME"] = U2NET_CACHE_DIR
    return env


def _run_autopipeline_subprocess(cmd: List[str], env: Dict[str, str]) -> subprocess.CompletedProcess[str]:
    logger.info(f"[MONTAGE] ▶️ Running autopipeline")
    logger.info(f"[MONTAGE] 📊 Command: {' '.join(cmd[:6])}...")
    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(VIDEO_EDITING_DIR),
    )
    duration = time.time() - start
    logger.info(f"[MONTAGE] ⏱️ Autopipeline finished in {duration:.2f}s (exit code {result.returncode})")
    return result


def _extract_overlay_cache(stderr: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    overlay_cache: Dict[str, str] = {}
    r2_cache: Dict[str, str] = {}
    for line in stderr.split("\n"):
        if "[AUTOPIPELINE] Generated overlay" not in line:
            continue
        try:
            parts = line.split("Generated overlay")[1].strip()
            shape, url = parts.split(":", 1)
            shape = shape.strip()
            url = url.strip()
            overlay_cache[shape] = url
            if "shotstack.io" in url:
                r2_cache[shape] = f"overlays/cache/{shape}_{int(time.time())}.mov"
        except Exception as exc:  # pragma: no cover - лог парсинг
            logger.warning(f"[MONTAGE] Failed to parse overlay log line '{line}': {exc}")
    return overlay_cache, r2_cache


def _cache_overlays(user_id: int, overlay_cache: Dict[str, str], r2_cache: Dict[str, str]) -> None:
    if not overlay_cache:
        return
    logger.info(f"[MONTAGE] Caching {len(overlay_cache)} overlay URLs for user {user_id}")
    from tg_bot.utils.user_state import set_cached_overlay_urls

    set_cached_overlay_urls(user_id, overlay_cache, r2_cache)


def _serialize_render_session(session: RenderSession) -> Dict[str, Any]:
    return {
        "id": session.id,
        "status": session.status,
        "scenario": session.scenario,
        "templates": session.templates or [],
        "subtitle_settings": session.subtitle_settings or {},
        "intro_settings": session.intro_settings or {},
        "outro_settings": session.outro_settings or {},
        "circle_settings": session.circle_settings or {},
        "head_r2_key": session.head_r2_key,
        "background_r2_key": session.background_r2_key,
        "result_r2_key": session.result_r2_key,
        "result_url": session.result_url,
        "shotstack_url": session.shotstack_url,
        "shotstack_render_id": session.shotstack_render_id,
        "error_message": session.error_message,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def _merge_session_settings(
    session: RenderSession,
    overrides: Dict[str, Any],
) -> Tuple[Sequence[str], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    merged_templates = _ensure_templates_list(overrides.get("templates") or session.templates)
    merged_subtitles = _normalize_subtitle_settings(session.subtitle_settings)
    merged_subtitles.update(overrides.get("subtitles", {}))
    merged_intro = _normalize_clip_settings(session.intro_settings)
    merged_intro.update(overrides.get("intro", {}))
    merged_outro = _normalize_clip_settings(session.outro_settings)
    merged_outro.update(overrides.get("outro", {}))
    merged_circle = _normalize_circle_settings(session.circle_settings)
    merged_circle.update(overrides.get("circle", {}))
    return merged_templates, merged_subtitles, merged_intro, merged_outro, merged_circle


async def _render_composite_session(
    user_id: int,
    *,
    head_r2_key: Optional[str],
    background_r2_key: Optional[str],
    templates: Sequence[str],
    subtitle_settings: Dict[str, Any],
    intro_settings: Dict[str, Any],
    outro_settings: Dict[str, Any],
    circle_settings: Dict[str, Any],
    render_session_id: Optional[int],
) -> Dict[str, str]:
    if not head_r2_key or not background_r2_key:
        raise VideoEditingError("Missing head/background assets for render session.")

    overall_start = time.time()
    render_session_ref = render_session_id

    try:
        head_url = get_presigned_url(head_r2_key, expiry_hours=1)
        bg_url = get_presigned_url(background_r2_key, expiry_hours=1)
        if not head_url or not bg_url:
            raise VideoEditingError("Failed to get presigned URLs for montage.")

        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            output_dir = tmpdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            manual_subtitles_path = _download_manual_subtitles(subtitle_settings, tmpdir)
            cmd = _build_autopipeline_command(
                background_url=bg_url,
                head_url=head_url,
                templates=templates,
                subtitle_settings=subtitle_settings,
                intro_settings=intro_settings,
                outro_settings=outro_settings,
                circle_settings=circle_settings,
                output_dir=output_dir,
                user_id=user_id,
                manual_subtitles_path=manual_subtitles_path,
            )
            env = _build_autopipeline_env()
            result = _run_autopipeline_subprocess(cmd, env)
            if result.returncode != 0:
                logger.error(f"[MONTAGE] ❌ Autopipeline failed with exit code {result.returncode}")
                logger.error(f"[MONTAGE] STDERR ({len(result.stderr)} chars): {result.stderr}")
                logger.error(f"[MONTAGE] STDOUT ({len(result.stdout)} chars): {result.stdout}")
                raise VideoEditingError(
                    f"Autopipeline failed (exit code {result.returncode}): {result.stderr[:500]}"
                )

            if result.stdout:
                lines = [l for l in result.stdout.split("\n") if l.strip()]
                logger.info(f"[MONTAGE] Last {min(20, len(lines))} lines of output:")
                for line in lines[-20:]:
                    logger.info(f"[MONTAGE]   {line}")
            if result.stderr:
                logger.info(f"[MONTAGE] STDERR output: {result.stderr}")

            video_url = extract_video_url_from_output(result.stdout)
            if not video_url:
                video_url = extract_video_url_from_output(result.stderr)
            if not video_url:
                raise VideoEditingError(
                    f"Failed to extract video URL from autopipeline output (checked {len(result.stdout) + len(result.stderr)} chars total)"
                )

            overlay_cache, r2_cache = _extract_overlay_cache(result.stderr)
            if overlay_cache:
                _cache_overlays(user_id, overlay_cache, r2_cache)

            result_file = Path(tmpdir) / f"composite_{user_id}_{int(time.time())}.mp4"
            if not download_video_from_url(video_url, str(result_file)):
                raise VideoEditingError("Failed to download rendered video from Shotstack")

            timestamp = int(time.time())
            result_r2_key = f"users/{user_id}/edited_videos/composite_{timestamp}.mp4"
            file_size = result_file.stat().st_size
            logger.info(f"[MONTAGE] 📊 Result file size: {format_size(file_size)}")
            if not upload_file(str(result_file), result_r2_key):
                raise VideoEditingError("Failed to upload result to R2")
            result_url = get_presigned_url(result_r2_key, expiry_hours=24)

            if render_session_ref:
                update_render_session_result(
                    render_session_ref,
                    status="success",
                    result_r2_key=result_r2_key,
                    result_url=result_url,
                    shotstack_url=video_url,
                )

            overall_duration = time.time() - overall_start
            minutes = int(overall_duration // 60)
            seconds = overall_duration % 60
            logger.info(
                f"[MONTAGE] ✅ Composite video ready: {result_r2_key} "
                f"({overall_duration:.2f}s, {minutes}m {seconds:.1f}s)"
            )
            return {"r2_key": result_r2_key, "url": result_url or ""}

    except Exception as exc:
        if render_session_ref:
            update_render_session_result(
                render_session_ref,
                status="error",
                error_message=str(exc),
            )
        raise
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
        start_time = time.time()
        logger.info(f"[MONTAGE] ▶️ Downloading video from Shotstack")
        
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        downloaded_bytes = 0
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded_bytes += len(chunk)
        
        duration = time.time() - start_time
        logger.info(f"[MONTAGE] ⏱️ Downloaded {format_size(downloaded_bytes)} in {duration:.2f}s")
        logger.info(f"[MONTAGE] 📊 Download speed: {format_size(int(downloaded_bytes / duration))}/s")
        
        return True
    except Exception as e:
        logger.error(f"[MONTAGE] ❌ Failed to download video: {e}")
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
    overall_start = time.time()
    
    try:
        logger.info(f"[MONTAGE] ▶️ Starting add_subtitles_to_video for user {user_id}")
        logger.info(f"[MONTAGE] 📊 Video: {video_r2_key}")
        logger.info(f"[MONTAGE] 📊 Transcript length: {len(text)} chars")
        
        # 1. Получить presigned URL для исходного видео
        start_time = time.time()
        logger.info(f"[MONTAGE] ▶️ Getting presigned URL from R2")
        head_url = get_presigned_url(video_r2_key, expiry_hours=1)
        if not head_url:
            raise VideoEditingError(f"Failed to get presigned URL for {video_r2_key}")
        logger.info(f"[MONTAGE] ⏱️ Got presigned URL in {time.time() - start_time:.2f}s")
        
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
            
            logger.info(f"[MONTAGE] ▶️ Running autopipeline subprocess")
            logger.info(f"[MONTAGE] 📊 Command: {' '.join(cmd[:6])}...")  # первые 6 аргументов
            
            # Установить переменные окружения
            env = os.environ.copy()
            env["SHOTSTACK_API_KEY"] = api_key
            env["SHOTSTACK_STAGE"] = stage
            # Оптимизации скорости
            env["SHOTSTACK_POLL_SECONDS"] = "3"  # чаще проверять статус рендера
            env["U2NET_HOME"] = "/tmp/.u2net"  # кэш rembg моделей
            
            subprocess_start = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(VIDEO_EDITING_DIR)
            )
            subprocess_duration = time.time() - subprocess_start
            logger.info(f"[MONTAGE] ⏱️ Autopipeline subprocess completed in {subprocess_duration:.2f}s")
            
            if result.returncode != 0:
                logger.error(f"[MONTAGE] ❌ Autopipeline failed with exit code {result.returncode}")
                logger.error(f"[MONTAGE] STDERR ({len(result.stderr)} chars): {result.stderr}")
                logger.error(f"[MONTAGE] STDOUT ({len(result.stdout)} chars): {result.stdout}")
                raise VideoEditingError(f"Autopipeline failed (exit code {result.returncode}): {result.stderr[:500]}")
            
            logger.info(f"[MONTAGE] ✅ Autopipeline completed successfully (exit code 0)")
            logger.info(f"[MONTAGE] 📊 Output: {len(result.stdout)} chars stdout, {len(result.stderr)} chars stderr")
            
            # Логируем последние 20 строк stdout для диагностики
            if result.stdout:
                lines = [l for l in result.stdout.split('\n') if l.strip()]
                logger.info(f"[MONTAGE] Last {min(20, len(lines))} lines of output:")
                for line in lines[-20:]:
                    logger.info(f"[MONTAGE]   {line}")
            
            if result.stderr:
                logger.info(f"[MONTAGE] STDERR output: {result.stderr}")
            
            # 4. Извлечь URL видео из вывода (проверяем и stdout и stderr)
            video_url = extract_video_url_from_output(result.stdout)
            if not video_url and result.stderr:
                # Попробуем найти в stderr (где находятся логи)
                video_url = extract_video_url_from_output(result.stderr)
            
            if not video_url:
                logger.error(f"[MONTAGE] ❌ Failed to extract video URL from autopipeline output")
                logger.error(f"[MONTAGE] 📊 Stdout ({len(result.stdout)} chars), Stderr ({len(result.stderr)} chars)")
                logger.error(f"[MONTAGE] Last 10 lines of stderr:")
                for line in result.stderr.split('\n')[-10:]:
                    if line.strip():
                        logger.error(f"[MONTAGE]   {line}")
                raise VideoEditingError(f"Failed to extract video URL from autopipeline output (checked {len(result.stdout) + len(result.stderr)} chars total)")
            
            logger.info(f"Extracted video URL: {video_url}")
            
            # 5. Скачать видео
            result_file = Path(tmpdir) / f"subtitled_{user_id}_{int(time.time())}.mp4"
            if not download_video_from_url(video_url, str(result_file)):
                raise VideoEditingError("Failed to download rendered video from Shotstack")
            
            logger.info(f"Downloaded video to: {result_file}")
            
            # 5. Загрузить результат в R2
            start_time = time.time()
            logger.info(f"[MONTAGE] ▶️ Uploading result to R2")
            
            timestamp = int(time.time())
            result_r2_key = f"users/{user_id}/edited_videos/subtitled_{timestamp}.mp4"
            
            file_size = result_file.stat().st_size
            logger.info(f"[MONTAGE] 📊 Result file size: {format_size(file_size)}")
            
            upload_success = upload_file(str(result_file), result_r2_key)
            if not upload_success:
                raise VideoEditingError("Failed to upload result to R2")
            
            upload_duration = time.time() - start_time
            logger.info(f"[MONTAGE] ⏱️ Uploaded to R2 in {upload_duration:.2f}s")
            logger.info(f"[MONTAGE] 📊 Upload speed: {format_size(int(file_size / upload_duration))}/s")
            
            # 6. Получить presigned URL для результата
            result_url = get_presigned_url(result_r2_key, expiry_hours=24)  # 24 часа
            
            overall_duration = time.time() - overall_start
            logger.info(f"[MONTAGE] ✅ Successfully created subtitled video: {result_r2_key}")
            
            # Итоговая статистика
            minutes = int(overall_duration // 60)
            seconds = overall_duration % 60
            logger.info(f"[MONTAGE] ⏱️ Total add_subtitles_to_video: {overall_duration:.2f}s ({minutes}m {seconds:.1f}s)")
            
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
    """Смонтировать видео с говорящей головой на фоне."""
    logger.info(f"[MONTAGE] ▶️ Starting composite render for user {user_id}")
    logger.info(f"[MONTAGE] 📊 Head video: {head_r2_key}")
    logger.info(f"[MONTAGE] 📊 Background video: {background_r2_key}")
    logger.info(f"[MONTAGE] 📊 Transcript length: {len(text)} chars")

    templates = _ensure_templates_list(DEFAULT_TEMPLATES)
    subtitle_settings = _normalize_subtitle_settings(
        {"mode": "auto", "theme": DEFAULT_SUBTITLE_THEME, "transcript": text}
    )
    intro_settings = _normalize_clip_settings(None)
    outro_settings = _normalize_clip_settings(None)
    circle_settings = _normalize_circle_settings(
        {
            "radius": float(os.getenv("OVERLAY_CIRCLE_RADIUS", "0.35")),
            "center_x": float(os.getenv("OVERLAY_CIRCLE_CENTER_X", "0.5")),
            "center_y": float(os.getenv("OVERLAY_CIRCLE_CENTER_Y", "0.5")),
            "auto_center": True,
        }
    )

    render_session = create_render_session(
        user_id,
        scenario=DEFAULT_SCENARIO,
        head_r2_key=head_r2_key,
        background_r2_key=background_r2_key,
        templates=templates,
        subtitle_settings=subtitle_settings,
        intro_settings=intro_settings,
        outro_settings=outro_settings,
        circle_settings=circle_settings,
    )
    if not render_session:
        raise VideoEditingError("Failed to persist render session for user.")

    return await _render_composite_session(
        user_id,
        head_r2_key=head_r2_key,
        background_r2_key=background_r2_key,
        templates=templates,
        subtitle_settings=subtitle_settings,
        intro_settings=intro_settings,
        outro_settings=outro_settings,
        circle_settings=circle_settings,
        render_session_id=render_session.id,
    )


def get_render_session_summary(user_id: int) -> Optional[Dict[str, Any]]:
    """Вернуть последнюю сессию монтажа для пользователя."""
    session = get_latest_render_session(user_id, scenario=DEFAULT_SCENARIO)
    if not session:
        return None
    return _serialize_render_session(session)


async def rerender_last_render_session(
    user_id: int,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Пересобрать видео с новыми настройками."""
    session = get_latest_render_session(user_id, scenario=DEFAULT_SCENARIO)
    if not session:
        raise VideoEditingError("Не найден предыдущий рендер для пользователя.")

    templates, subtitles, intro_settings, outro_settings, circle_settings = _merge_session_settings(
        session,
        overrides or {},
    )

    new_session = create_render_session(
        user_id,
        scenario=session.scenario,
        head_r2_key=session.head_r2_key,
        background_r2_key=session.background_r2_key,
        templates=templates,
        subtitle_settings=subtitles,
        intro_settings=intro_settings,
        outro_settings=outro_settings,
        circle_settings=circle_settings,
    )
    if not new_session:
        raise VideoEditingError("Не удалось создать новую сессию монтажа.")

    return await _render_composite_session(
        user_id,
        head_r2_key=new_session.head_r2_key,
        background_r2_key=new_session.background_r2_key,
        templates=templates,
        subtitle_settings=subtitles,
        intro_settings=intro_settings,
        outro_settings=outro_settings,
        circle_settings=circle_settings,
        render_session_id=new_session.id,
    )
