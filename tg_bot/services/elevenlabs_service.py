"""ElevenLabs TTS utilities."""
import os, uuid, pathlib, asyncio
from typing import Iterable

from elevenlabs import ElevenLabs

API_KEY = os.environ.get("ELEVEN_API_KEY") or os.environ.get("ELEVENLABS_API_KEY", "")

AUDIO_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Заглушечный список не используется для сэмплов (они читаются из файлов).
DEFAULT_VOICES = [
    ("Ava",   "EXAMPLE_VOICE_ID_1"),
    ("Noah",  "EXAMPLE_VOICE_ID_2"),
]


def _synth_sync(text: str, voice_id: str, outfile: str) -> str:
    if not API_KEY:
        raise ValueError("ELEVEN_API_KEY or ELEVENLABS_API_KEY not set in environment")
    client = ElevenLabs(api_key=API_KEY)
    audio: Iterable[bytes] = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    with open(outfile, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    return outfile


async def tts_to_file(text: str, voice_id: str) -> str:
    """Synthesize speech via ElevenLabs and save to file, returning path."""
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    out_path = str(AUDIO_DIR / filename)
    return await asyncio.to_thread(_synth_sync, text, voice_id, out_path)
