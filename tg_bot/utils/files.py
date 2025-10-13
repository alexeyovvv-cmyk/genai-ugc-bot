# files.py — утилиты для стартовых кадров
import pathlib, glob
from typing import List

IMG_DIR = pathlib.Path("data/start_frames")

def list_start_frames() -> List[str]:
    return sorted(glob.glob(str(IMG_DIR / "*.*")))[:10]  # первые 10
