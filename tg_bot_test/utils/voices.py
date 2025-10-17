import glob
import pathlib
from typing import List, Tuple, Optional

from tg_bot.config import BASE_DIR

VOICES_DIR = BASE_DIR / "data" / "audio" / "voices"


def list_voice_samples(gender: str = None, age: str = None, page: int = 0, limit: int = 5) -> Tuple[List[Tuple[str, str, str]], bool]:
    """
    Получить список голосов с пагинацией
    
    Args:
        gender: 'male' или 'female' (если None, то все полы)
        age: 'young', 'elderly' (если None, то все возрасты)
        page: номер страницы (начиная с 0)
        limit: количество голосов на странице
    
    Returns:
        Tuple[List[Tuple[str, str, str]], bool]: 
            (список (name, voice_id, path), есть_ли_следующая_страница)
    """
    try:
        if gender and age:
            # Получаем голоса для конкретной категории
            target_dir = VOICES_DIR / gender / age
            if not target_dir.exists():
                return [], False
            paths = sorted(glob.glob(str(target_dir / "*.mp3")))
        else:
            # Получаем все голоса всех категорий (для настроек)
            paths = []
            for gender_dir in VOICES_DIR.iterdir():
                if gender_dir.is_dir():
                    for age_dir in gender_dir.iterdir():
                        if age_dir.is_dir():
                            paths.extend(sorted(glob.glob(str(age_dir / "*.mp3"))))
            paths = sorted(paths)
        
        # Парсим файлы
        result: List[Tuple[str, str, str]] = []
        for p in paths:
            fname = pathlib.Path(p).stem
            # Поддерживаем два формата именования:
            # 1) "Name__<voice_id>" — старый формат с двойным подчеркиванием
            # 2) "Name_<voice_id>" — новый формат с одиночным подчеркиванием
            if "__" in fname:
                name, voice_id = fname.split("__", 1)
            else:
                # Пробуем отделить voice_id по последнему '_' если правая часть похожа на ID
                if "_" in fname:
                    name_part, maybe_id = fname.rsplit("_", 1)
                    # Heuristics: ID обычно длинная последовательность [A-Za-z0-9] (>=16 символов)
                    if maybe_id.isalnum() and len(maybe_id) >= 16:
                        name, voice_id = name_part, maybe_id
                    else:
                        name, voice_id = fname, fname
                else:
                    name, voice_id = fname, fname
            result.append((name, voice_id, p))
        
        # Применяем пагинацию
        start_idx = page * limit
        end_idx = start_idx + limit
        
        page_voices = result[start_idx:end_idx]
        has_next = end_idx < len(result)
        
        return page_voices, has_next
        
    except Exception as e:
        print(f"Error listing voice samples: {e}")
        return [], False


def get_voice_sample(gender: str, age: str, index: int) -> Optional[Tuple[str, str, str]]:
    """
    Получить конкретный голос по индексу
    
    Args:
        gender: 'male' или 'female'
        age: 'young', 'elderly'
        index: индекс голоса
    
    Returns:
        Optional[Tuple[str, str, str]]: (name, voice_id, path) или None
    """
    try:
        voices, _ = list_voice_samples(gender, age, page=0, limit=1000)  # Получаем все
        if 0 <= index < len(voices):
            return voices[index]
        return None
    except Exception as e:
        print(f"Error getting voice sample: {e}")
        return None


def list_all_voice_samples() -> List[Tuple[str, str, str]]:
    """
    Получить все голоса всех категорий (для обратной совместимости и настроек)
    
    Returns:
        List[Tuple[str, str, str]]: список (name, voice_id, path)
    """
    voices, _ = list_voice_samples(page=0, limit=10000)  # Большой лимит чтобы получить все
    return voices


