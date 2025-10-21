# files.py — утилиты для персонажей
import pathlib, glob
from typing import List, Tuple, Optional
from datetime import datetime, timedelta

from tg_bot.config import BASE_DIR
from tg_bot.services.r2_service import list_files, get_presigned_url

# Структура персонажей
CHARACTERS_DIR = BASE_DIR / "data" / "characters"

# Cache for presigned URLs to avoid repeated API calls
_url_cache = {}
_cache_expiry = {}

def list_character_images(gender: str, age: str, page: int = 0, limit: int = 5) -> Tuple[List[str], bool]:
    """
    Получить список изображений персонажей с пагинацией
    
    Args:
        gender: 'male' или 'female'
        age: 'young', 'elderly'
        page: номер страницы (начиная с 0)
        limit: количество изображений на странице
    
    Returns:
        Tuple[List[str], bool]: (список путей к изображениям, есть_ли_следующая_страница)
    """
    try:
        # Сначала пробуем получить из R2
        r2_prefix = f"presets/characters/{gender}/{age}/"
        r2_files = list_files(r2_prefix)
        
        if r2_files:
            # Фильтруем только изображения
            image_files = [f for f in r2_files if f['key'].lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            # Применяем пагинацию
            start_idx = page * limit
            end_idx = start_idx + limit
            
            page_images = image_files[start_idx:end_idx]
            has_next = end_idx < len(image_files)
            
            # Возвращаем R2 ключи вместо локальных путей
            return [f['key'] for f in page_images], has_next
        
        # Fallback к локальным файлам
        target_dir = CHARACTERS_DIR / gender / age
        
        if not target_dir.exists():
            return [], False
        
        # Получаем все изображения
        all_images = sorted(glob.glob(str(target_dir / "*.*")))
        
        # Применяем пагинацию
        start_idx = page * limit
        end_idx = start_idx + limit
        
        page_images = all_images[start_idx:end_idx]
        has_next = end_idx < len(all_images)
        
        return page_images, has_next
        
    except Exception as e:
        print(f"Error listing character images: {e}")
        return [], False

def get_character_image(gender: str, age: str, index: int) -> Optional[str]:
    """
    Получить конкретное изображение персонажа по индексу
    
    Args:
        gender: 'male' или 'female'
        age: 'young', 'elderly'
        index: индекс изображения
    
    Returns:
        str: путь к изображению или None
    """
    try:
        images, _ = list_character_images(gender, age, page=0, limit=1000)  # Получаем все
        if 0 <= index < len(images):
            return images[index]
        return None
    except Exception as e:
        print(f"Error getting character image: {e}")
        return None

def get_character_image_url(r2_key: str, expiry_hours: int = 1) -> Optional[str]:
    """
    Получить presigned URL для изображения персонажа
    
    Args:
        r2_key: R2 ключ изображения
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
        print(f"Error getting character image URL: {e}")
        return None

def get_available_genders() -> List[str]:
    """Получить доступные полы"""
    try:
        if not CHARACTERS_DIR.exists():
            return []
        
        genders = []
        for item in CHARACTERS_DIR.iterdir():
            if item.is_dir():
                genders.append(item.name)
        return sorted(genders)
    except Exception as e:
        print(f"Error getting genders: {e}")
        return []

def get_available_ages(gender: str) -> List[str]:
    """Получить доступные возрасты для пола"""
    try:
        gender_dir = CHARACTERS_DIR / gender
        if not gender_dir.exists():
            return []
        
        ages = []
        for item in gender_dir.iterdir():
            if item.is_dir():
                ages.append(item.name)
        return sorted(ages)
    except Exception as e:
        print(f"Error getting ages: {e}")
        return []
