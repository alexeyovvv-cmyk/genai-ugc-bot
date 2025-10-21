#!/usr/bin/env python3
"""
Тестовый скрипт для проверки nano-banana API
"""
import asyncio
import os
from dotenv import load_dotenv
from tg_bot.services.nano_banana_service import edit_character_image

load_dotenv()

async def test_nano_banana():
    """Тестируем nano-banana API с реальным изображением"""
    print("🧪 Тестируем nano-banana API...")
    
    # Проверяем FAL_KEY
    fal_key = os.getenv('FAL_KEY') or os.getenv('FALAI_API_TOKEN')
    if not fal_key:
        print("❌ FAL_KEY не найден в переменных окружения")
        return False
    
    print(f"✅ FAL_KEY найден: {fal_key[:10]}...")
    
    # Ищем тестовое изображение персонажа
    test_image_path = None
    characters_dir = "data/characters"
    
    for gender in ["male", "female"]:
        for age in ["young", "elderly"]:
            gender_dir = os.path.join(characters_dir, gender, age)
            if os.path.exists(gender_dir):
                images = [f for f in os.listdir(gender_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
                if images:
                    test_image_path = os.path.join(gender_dir, images[0])
                    print(f"✅ Найдено тестовое изображение: {test_image_path}")
                    break
        if test_image_path:
            break
    
    if not test_image_path:
        print("❌ Не найдено тестовое изображение персонажа")
        return False
    
    # Тестируем редактирование
    test_prompt = "add sunglasses"
    print(f"🎨 Тестируем редактирование с промптом: '{test_prompt}'")
    print(f"📷 Исходное изображение: {test_image_path}")
    
    try:
        result_path = await edit_character_image(test_image_path, test_prompt)
        
        if result_path:
            print(f"✅ Редактирование успешно!")
            print(f"📁 Результат сохранен: {result_path}")
            
            # Проверяем, что файл существует
            if os.path.exists(result_path):
                file_size = os.path.getsize(result_path)
                print(f"📊 Размер файла: {file_size} байт")
                return True
            else:
                print("❌ Файл результата не найден")
                return False
        else:
            print("❌ Редактирование не удалось")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_nano_banana())
    if success:
        print("\n🎉 Тест nano-banana API прошел успешно!")
    else:
        print("\n💥 Тест nano-banana API не прошел")
