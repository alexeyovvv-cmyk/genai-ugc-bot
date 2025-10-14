#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы модуля улучшения видео промптов.

Использование:
    python test_video_prompt_enhancer.py "Текст для улучшения"
    
или для интерактивного режима:
    python test_video_prompt_enhancer.py
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Импортируем наш сервис
from tg_bot.services.prompt_enhancer_service import enhance_video_prompt


async def test_enhancement(text: str):
    """Тестирует улучшение видео промпта."""
    print("=" * 80)
    print("🎬 Тестирование Video Prompt Enhancer")
    print("=" * 80)
    print()
    
    # Проверяем наличие API ключа
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ОШИБКА: OPENAI_API_KEY не установлен!")
        print()
        print("Установите переменную окружения:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print()
        print("или добавьте в файл .env:")
        print("  OPENAI_API_KEY=your-key-here")
        print()
        return
    
    print(f"✅ API ключ найден: {api_key[:10]}...")
    print()
    
    print("📝 Исходный текст:")
    print(f"   {text}")
    print()
    
    print("⏳ Улучшаю и перевожу промпт для видео...")
    print()
    
    try:
        enhanced = await enhance_video_prompt(text)
        
        print("✅ Результат:")
        print("=" * 80)
        print()
        print("📥 ИСХОДНОЕ ОПИСАНИЕ:")
        print(f"   {text}")
        print()
        print("📤 УЛУЧШЕННЫЙ ПРОМПТ (для AI видео):")
        print(f"   {enhanced}")
        print()
        print("=" * 80)
        
        # Показываем статистику
        original_len = len(text)
        enhanced_len = len(enhanced)
        diff = enhanced_len - original_len
        
        print()
        print("📊 Статистика:")
        print(f"   Длина исходного: {original_len} символов")
        print(f"   Длина улучшенного: {enhanced_len} символов")
        print(f"   Изменение: {diff:+d} символов ({diff/original_len*100:+.1f}%)")
        print()
        
        # Анализ улучшений
        if text == enhanced:
            print("⚠️  Текст не изменился (возможно, ошибка API или текст уже оптимален)")
        else:
            print("✅ Промпт успешно улучшен!")
            
            # Проверяем, добавлены ли ключевые элементы
            enhancements_found = []
            
            keywords = {
                "Освещение": ["lighting", "light", "golden hour", "sunset", "sunrise", "dramatic"],
                "Камера": ["shot", "camera", "angle", "close-up", "wide", "tracking", "cinematic"],
                "Качество": ["4K", "quality", "detailed", "professional", "high"],
                "Атмосфера": ["atmosphere", "mood", "vibrant", "calm", "energetic"],
                "Движение": ["motion", "moving", "dynamic", "slow", "fast"]
            }
            
            enhanced_lower = enhanced.lower()
            for category, words in keywords.items():
                if any(word in enhanced_lower for word in words):
                    enhancements_found.append(category)
            
            if enhancements_found:
                print()
                print("🎨 Добавленные элементы:")
                for enhancement in enhancements_found:
                    print(f"   ✓ {enhancement}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def interactive_mode():
    """Интерактивный режим тестирования."""
    print("=" * 80)
    print("🎬 Video Prompt Enhancer - Интерактивный режим")
    print("=" * 80)
    print()
    print("Введите описание ситуации для видео (или 'q' для выхода):")
    print()
    
    while True:
        try:
            text = input(">>> ").strip()
            
            if not text:
                continue
                
            if text.lower() in ['q', 'quit', 'exit']:
                print("👋 До свидания!")
                break
            
            await test_enhancement(text)
            print()
            print("Введите следующее описание (или 'q' для выхода):")
            print()
            
        except KeyboardInterrupt:
            print()
            print("👋 До свидания!")
            break
        except EOFError:
            break


async def main():
    """Главная функция."""
    # Если передан аргумент командной строки - используем его
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        await test_enhancement(text)
    else:
        # Иначе запускаем интерактивный режим
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())

