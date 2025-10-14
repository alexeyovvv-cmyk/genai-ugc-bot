#!/usr/bin/env python3
"""
Тестовый скрипт для проверки новой системы персонажей
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tg_bot.utils.files import (
    list_character_images,
    get_character_image,
    get_available_genders,
    get_available_ages
)

def test_character_system():
    """Тестируем новую систему персонажей"""
    print("🧪 Тестирование новой системы персонажей")
    print("=" * 50)
    
    # Тест 1: Получение доступных полов
    print("\n1️⃣ Тестируем получение доступных полов:")
    genders = get_available_genders()
    print(f"   Доступные полы: {genders}")
    
    # Тест 2: Получение доступных возрастов для каждого пола
    print("\n2️⃣ Тестируем получение доступных возрастов:")
    for gender in genders:
        ages = get_available_ages(gender)
        print(f"   {gender}: {ages}")
    
    # Тест 3: Получение изображений с пагинацией
    print("\n3️⃣ Тестируем получение изображений с пагинацией:")
    for gender in genders:
        ages = get_available_ages(gender)
        for age in ages:
            print(f"\n   📁 {gender}/{age}:")
            images, has_next = list_character_images(gender, age, page=0, limit=5)
            print(f"      Изображений на странице: {len(images)}")
            print(f"      Есть следующая страница: {has_next}")
            
            for i, img_path in enumerate(images):
                print(f"      {i+1}. {os.path.basename(img_path)}")
    
    # Тест 4: Получение конкретного изображения
    print("\n4️⃣ Тестируем получение конкретного изображения:")
    for gender in genders:
        ages = get_available_ages(gender)
        for age in ages:
            images, _ = list_character_images(gender, age, page=0, limit=1000)
            if images:
                # Получаем первое изображение
                img = get_character_image(gender, age, 0)
                if img:
                    print(f"   ✅ {gender}/{age}[0]: {os.path.basename(img)}")
                else:
                    print(f"   ❌ {gender}/{age}[0]: не найдено")
                break
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    test_character_system()
