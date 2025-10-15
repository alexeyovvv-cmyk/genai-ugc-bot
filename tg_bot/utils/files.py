# files.py — утилиты для персонажей
import pathlib, glob
from typing import List, Tuple, Optional

# Структура персонажей
CHARACTERS_DIR = pathlib.Path("data/characters")

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
        # Путь к папке с персонажами
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
