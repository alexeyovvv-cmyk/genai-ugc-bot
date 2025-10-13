import glob
import pathlib
from typing import List, Tuple


VOICES_DIR = pathlib.Path("data/audio/voices")


def list_voice_samples() -> List[Tuple[str, str, str]]:
    """Return list of (name, voice_id, path) for available mp3 samples.
    Filename formats supported:
      - Name__VOICEID.mp3  -> name=Name, voice_id=VOICEID
      - Name.mp3           -> name=Name, voice_id=Name
    """
    paths = sorted(glob.glob(str(VOICES_DIR / "*.mp3")))
    result: List[Tuple[str, str, str]] = []
    for p in paths:
        fname = pathlib.Path(p).stem
        if "__" in fname:
            name, voice_id = fname.split("__", 1)
        else:
            name, voice_id = fname, fname
        result.append((name, voice_id, p))
    return result


