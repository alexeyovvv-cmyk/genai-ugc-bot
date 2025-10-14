#!/usr/bin/env python3
"""
Тест улучшателя промптов с эмоциональными тегами для ElevenLabs v3.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from tg_bot.services.prompt_enhancer_service import enhance_audio_prompt


async def test():
    print("=" * 80)
    print("🎤 Тест эмоциональных тегов для ElevenLabs v3")
    print("=" * 80)
    print()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY не установлен!")
        return
    
    print(f"✅ API ключ найден: {api_key[:10]}...")
    print()
    
    test_texts = [
        "Привет! Попробуй наш продукт со скидкой!",
        "Купите наш новый продукт сегодня",
        "Это потрясающее предложение только для вас"
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"📝 Пример {i}:")
        print(f"Исходный: {text}")
        print()
        
        enhanced = await enhance_audio_prompt(text)
        
        print(f"✅ Улучшенный: {enhanced}")
        print()
        
        # Показываем найденные теги
        import re
        tags = re.findall(r'\[(.*?)\]', enhanced)
        if tags:
            print(f"🎭 Найденные теги: {', '.join([f'[{tag}]' for tag in tags])}")
        else:
            print("⚠️  Теги не найдены!")
        
        print("-" * 80)
        print()
    
    print("💡 Эти теги будут переданы в ElevenLabs модель eleven_v3")
    print("   для эмоциональной озвучки!")
    print()


if __name__ == "__main__":
    asyncio.run(test())

