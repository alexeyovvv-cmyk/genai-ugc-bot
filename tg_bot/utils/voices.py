import glob
import pathlib
from typing import List, Tuple, Optional
from datetime import datetime, timedelta

from tg_bot.config import BASE_DIR
from tg_bot.services.r2_service import list_files, get_presigned_url

VOICES_DIR = BASE_DIR / "data" / "audio" / "voices"

# Cache for presigned URLs to avoid repeated API calls
_url_cache = {}
_cache_expiry = {}


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
            (список (name, voice_id, r2_key), есть_ли_следующая_страница)
    """
    try:
        if gender and age:
            # Сначала пробуем получить из R2
            r2_prefix = f"presets/voices/{gender}/{age}/"
            r2_files = list_files(r2_prefix)
            
            if r2_files:
                # Фильтруем только MP3 файлы
                mp3_files = [f for f in r2_files if f['key'].lower().endswith('.mp3')]
                
                # Парсим файлы
                result: List[Tuple[str, str, str]] = []
                for file_info in mp3_files:
                    fname = pathlib.Path(file_info['key']).stem
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
                    result.append((name, voice_id, file_info['key']))
                
                # Применяем пагинацию
                start_idx = page * limit
                end_idx = start_idx + limit
                
                page_voices = result[start_idx:end_idx]
                has_next = end_idx < len(result)
                
                return page_voices, has_next
        
        # Fallback к локальным файлам
        if gender and age:
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
        Optional[Tuple[str, str, str]]: (name, voice_id, local_path) или None
    """
    try:
        voices, _ = list_voice_samples(gender, age, page=0, limit=1000)  # Получаем все
        if 0 <= index < len(voices):
            name, voice_id, voice_key = voices[index]
            
            # Если это R2 ключ, скачиваем файл во временную папку
            if voice_key.startswith('presets/'):
                from tg_bot.services.r2_service import download_file
                import tempfile
                import os
                
                # Создаем временный файл
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                    temp_path = temp_file.name
                
                # Скачиваем файл из R2
                if download_file(voice_key, temp_path):
                    return (name, voice_id, temp_path)
                else:
                    print(f"Failed to download R2 file: {voice_key}")
                    return None
            else:
                # Это локальный путь
                return (name, voice_id, voice_key)
        return None
    except Exception as e:
        print(f"Error getting voice sample: {e}")
        return None

def get_voice_sample_url(r2_key: str, expiry_hours: int = 1) -> Optional[str]:
    """
    Получить presigned URL для голосового сэмпла
    
    Args:
        r2_key: R2 ключ аудио файла
        expiry_hours: время жизни URL в часах
    
    Returns:
        Optional[str]: presigned URL или None
    """
    try:
        # Проверяем кэш
        cache_key = f"{r2_key}_{expiry_hours}"
        now = datetime.now()
        
        if cache_key in _url_cache and cache_key in _cache_expiry:
            if now < _cache_expiry[cache_key]:
                return _url_cache[cache_key]
        
        # Генерируем новый URL
        url = get_presigned_url(r2_key, expiry_hours)
        
        if url:
            # Кэшируем URL
            _url_cache[cache_key] = url
            _cache_expiry[cache_key] = now + timedelta(hours=expiry_hours - 0.1)  # Небольшой запас
        
        return url
        
    except Exception as e:
        print(f"Error getting voice sample URL: {e}")
        return None


def list_all_voice_samples() -> List[Tuple[str, str, str]]:
    """
    Получить все голоса всех категорий (для обратной совместимости и настроек)
    
    Returns:
        List[Tuple[str, str, str]]: список (name, voice_id, path)
    """
    voices, _ = list_voice_samples(page=0, limit=10000)  # Большой лимит чтобы получить все
    return voices


