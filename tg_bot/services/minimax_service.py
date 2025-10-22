"""MiniMax TTS utilities via fal.ai."""
import os
import uuid
import pathlib
import asyncio
import time
import requests
from typing import Optional

from tg_bot.services.r2_service import upload_file
from tg_bot.utils.logger import setup_logger
from tg_bot.config import BASE_DIR

logger = setup_logger(__name__)

# Use the same FAL_KEY as video generation
FAL_API_KEY = os.environ.get("FALAI_API_TOKEN") or os.environ.get("FAL_KEY", "")

AUDIO_DIR = BASE_DIR / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _synth_sync(text: str, voice_id: str, language: str = "auto", emotion: str = "neutral") -> str:
    """Synchronous TTS generation using fal.ai MiniMax API."""
    import sys
    
    if not FAL_API_KEY:
        sys.stderr.write("[TTS] ❌ FAL API KEY не найден!\n")
        sys.stderr.flush()
        raise ValueError("FALAI_API_TOKEN or FAL_KEY not set in environment")
    
    sys.stderr.write(f"[TTS] Создаем fal.ai клиента для MiniMax...\n")
    sys.stderr.flush()
    
    try:
        import fal_client
        
        # Configure fal_client with API key
        os.environ["FAL_KEY"] = FAL_API_KEY
        
        sys.stderr.write(f"[TTS] Вызываем fal.ai MiniMax API...\n")
        sys.stderr.flush()
        
        # Prepare input parameters for MiniMax Speech-02 Turbo
        input_params = {
            "text": text,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1,
                "vol": 1,
                "pitch": 0,
                "emotion": emotion,
                "english_normalization": False
            },
            "language_boost": language,
            "output_format": "url"
        }
        
        sys.stderr.write(f"[TTS] Voice ID: {voice_id}, Language: {language}, Emotion: {emotion}\n")
        sys.stderr.flush()
        
        # Call fal.ai MiniMax API
        result = fal_client.subscribe(
            "fal-ai/minimax/speech-02-turbo",
            arguments=input_params,
            with_logs=True,
        )
        
        sys.stderr.write(f"[TTS] ✅ MiniMax API успешно выполнен\n")
        sys.stderr.flush()
        
        # Extract audio URL from result
        audio_url = None
        if isinstance(result, dict):
            if 'audio' in result:
                audio_data = result['audio']
                if isinstance(audio_data, dict) and 'url' in audio_data:
                    audio_url = audio_data['url']
                elif isinstance(audio_data, str):
                    audio_url = audio_data
            elif 'url' in result:
                audio_url = result['url']
        
        if not audio_url:
            sys.stderr.write(f"[TTS] ❌ Не найден URL аудио в результате: {result}\n")
            sys.stderr.flush()
            logger.error(f"[TTS] Audio URL not found in MiniMax response: {result}")
            raise ValueError("Audio URL not found in API response")
        
        sys.stderr.write(f"[TTS] Скачиваем аудио с URL: {audio_url}\n")
        sys.stderr.flush()
        
        # Download audio from URL
        response = requests.get(audio_url, timeout=60)
        response.raise_for_status()
        audio_data = response.content
        
        if not audio_data:
            raise ValueError("No audio data received")
        
        # Generate unique filename
        filename = f"minimax_{uuid.uuid4().hex}.mp3"
        out_path = str(AUDIO_DIR / filename)
        
        # Save audio file
        with open(out_path, "wb") as f:
            f.write(audio_data)
        
        sys.stderr.write(f"[TTS] ✅ Аудио сохранено: {out_path}\n")
        sys.stderr.flush()
        
        return out_path
        
    except ImportError:
        sys.stderr.write("[TTS] ❌ fal-client пакет не установлен. Установите: pip install fal-client\n")
        sys.stderr.flush()
        raise ImportError("fal-client package not installed")
    except Exception as e:
        sys.stderr.write(f"[TTS] ❌ Ошибка в MiniMax генерации: {e}\n")
        sys.stderr.flush()
        # Логируем полную ошибку для разработки, но не показываем пользователю
        logger.error(f"[TTS] MiniMax API error: {e}")
        
        # Преобразуем технические ошибки в понятные для пользователя
        if "Exhausted balance" in str(e) or "User is locked" in str(e):
            raise Exception("TTS service temporarily unavailable")
        elif "API" in str(e) or "fal.ai" in str(e):
            raise Exception("TTS service error")
        else:
            raise


async def tts_to_file(text: str, voice_id: str, language: str = "auto", emotion: str = "neutral", user_id: Optional[int] = None) -> str:
    """Synthesize speech via MiniMax fal.ai and save to file, returning path."""
    import sys
    logger.info(f"[TTS] Начинаем генерацию MiniMax TTS для текста: '{text[:50]}...'")
    sys.stderr.write(f"[TTS] Voice ID: {voice_id}, Language: {language}, Emotion: {emotion}\n")
    sys.stderr.flush()
    
    filename = f"minimax_{uuid.uuid4().hex}.mp3"
    out_path = str(AUDIO_DIR / filename)
    
    logger.info(f"[TTS] Путь для сохранения: {out_path}")
    sys.stderr.write(f"[TTS] Вызываем fal.ai MiniMax API...\n")
    sys.stderr.flush()
    
    result = await asyncio.to_thread(_synth_sync, text, voice_id, language, emotion)
    
    logger.info(f"[TTS] ✅ MiniMax TTS завершен успешно: {result}")
    sys.stderr.write(f"[TTS] ✅ Файл создан\n")
    sys.stderr.flush()
    
    # Upload to R2 if user_id provided
    if user_id:
        try:
            timestamp = int(time.time())
            r2_key = f"temp/{user_id}_{timestamp}/{filename}"
            
            logger.info(f"[TTS] Uploading to R2: {r2_key}")
            if upload_file(result, r2_key):
                logger.info(f"[TTS] ✅ Uploaded to R2: {r2_key}")
            else:
                logger.warning(f"[TTS] ⚠️ Failed to upload to R2, keeping local file")
        except Exception as e:
            logger.warning(f"[TTS] ⚠️ R2 upload error: {e}")
    
    return result
