#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы модуля улучшения промптов.

Использование:
    python test_prompt_enhancer.py "Текст для улучшения"
    
или для интерактивного режима:
    python test_prompt_enhancer.py
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Импортируем наш сервис
from tg_bot.services.prompt_enhancer_service import enhance_audio_prompt


async def test_enhancement(text: str):
    """Тестирует улучшение промпта."""
    print("=" * 80)
    print("🧪 Тестирование Prompt Enhancer")
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
    
    print("⏳ Улучшаю промпт...")
    print()
    
    try:
        enhanced = await enhance_audio_prompt(text)
        
        print("✅ Результат:")
        print("=" * 80)
        print()
        print("📥 ИСХОДНЫЙ ТЕКСТ:")
        print(f"   {text}")
        print()
        print("📤 УЛУЧШЕННЫЙ ТЕКСТ:")
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
        
        if text == enhanced:
            print("⚠️  Текст не изменился (возможно, ошибка API или текст уже оптимален)")
        else:
            print("✅ Текст успешно улучшен!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def interactive_mode():
    """Интерактивный режим тестирования."""
    print("=" * 80)
    print("🧪 Prompt Enhancer - Интерактивный режим")
    print("=" * 80)
    print()
    print("Введите текст для улучшения (или 'q' для выхода):")
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
            print("Введите следующий текст (или 'q' для выхода):")
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

