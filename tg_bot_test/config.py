import os
import pathlib

# Resolve BASE_DIR from env or default to current working directory
BASE_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")).resolve()

# Prefer DATABASE_URL_TEST from env; otherwise use sqlite file under BASE_DIR
# Для тестового бота используем отдельную БД
DATABASE_URL = os.getenv("DATABASE_URL_TEST") or f"sqlite:///{(BASE_DIR / 'genai_test.db').as_posix()}"


def ensure_dirs() -> None:
    """Create expected data directories under BASE_DIR if missing."""
    for p in [
        BASE_DIR / "data",
        BASE_DIR / "data" / "audio",
        BASE_DIR / "data" / "audio" / "voices",
        BASE_DIR / "data" / "characters",
        BASE_DIR / "data" / "video",
    ]:
        p.mkdir(parents=True, exist_ok=True)


