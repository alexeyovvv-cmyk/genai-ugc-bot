"""ElevenLabs TTS utilities."""
import os, uuid, pathlib, asyncio, time
from typing import Iterable, Optional

from elevenlabs import ElevenLabs
from tg_bot.services.r2_service import upload_file
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

API_KEY = os.environ.get("ELEVEN_API_KEY") or os.environ.get("ELEVENLABS_API_KEY", "")

AUDIO_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)



def _synth_sync(text: str, voice_id: str, outfile: str) -> str:
    import sys
    
    if not API_KEY:
        sys.stderr.write("[TTS] ❌ API KEY не найден!\n")
        sys.stderr.flush()
        raise ValueError("ELEVEN_API_KEY or ELEVENLABS_API_KEY not set in environment")
    
    sys.stderr.write(f"[TTS] Создаем ElevenLabs клиента...\n")
    sys.stderr.flush()
    
    client = ElevenLabs(api_key=API_KEY)
    
    sys.stderr.write(f"[TTS] Вызываем text_to_speech.convert...\n")
    sys.stderr.flush()
    
    audio: Iterable[bytes] = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    
    sys.stderr.write(f"[TTS] Сохраняем аудио в файл {outfile}...\n")
    sys.stderr.flush()
    
    with open(outfile, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    
    sys.stderr.write(f"[TTS] ✅ Файл сохранен\n")
    sys.stderr.flush()
    
    return outfile


async def tts_to_file(text: str, voice_id: str, user_id: Optional[int] = None) -> str:
    """Synthesize speech via ElevenLabs and save to file, returning path."""
    import sys
    logger.info(f"[TTS] Начинаем генерацию TTS для текста: '{text[:50]}...'")
    sys.stderr.write(f"[TTS] Voice ID: {voice_id}\n")
    sys.stderr.flush()
    
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    out_path = str(AUDIO_DIR / filename)
    
    logger.info(f"[TTS] Путь для сохранения: {out_path}")
    sys.stderr.write(f"[TTS] Вызываем API ElevenLabs...\n")
    sys.stderr.flush()
    
    result = await asyncio.to_thread(_synth_sync, text, voice_id, out_path)
    
    logger.info(f"[TTS] ✅ TTS завершен успешно: {result}")
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
