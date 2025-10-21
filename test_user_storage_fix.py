#!/usr/bin/env python3
"""
Тест исправления преобразования TG ID в внутренний ID в user_storage.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tg_bot.utils.user_storage import save_user_generation, get_user_generations, get_user_storage_stats
from tg_bot.db import SessionLocal
from tg_bot.models import User, GenerationHistory
from sqlalchemy import select

def test_user_id_conversion():
    """Тест преобразования TG ID в внутренний ID"""
    print("🧪 Тестирование преобразования TG ID в внутренний ID...")
    
    # Получаем тестового пользователя
    with SessionLocal() as db:
        user = db.execute(select(User).first()).scalar_one_or_none()
        if not user:
            print("❌ Пользователи не найдены в базе данных")
            return False
        
        tg_id = user.tg_id
        internal_id = user.id
        print(f"📊 Найден пользователь: TG ID = {tg_id}, Internal ID = {internal_id}")
        
        # Тест 1: save_user_generation
        print("\n1️⃣ Тестирование save_user_generation...")
        generation_id = save_user_generation(
            user_id=tg_id,  # Используем TG ID
            generation_type="test",
            text_prompt="Test prompt",
            credits_spent=1
        )
        
        if generation_id:
            print(f"✅ save_user_generation успешно: ID = {generation_id}")
        else:
            print("❌ save_user_generation не удалось")
            return False
        
        # Тест 2: get_user_generations
        print("\n2️⃣ Тестирование get_user_generations...")
        generations = get_user_generations(user_id=tg_id, limit=5)
        print(f"✅ get_user_generations успешно: найдено {len(generations)} генераций")
        
        # Тест 3: get_user_storage_stats
        print("\n3️⃣ Тестирование get_user_storage_stats...")
        stats = get_user_storage_stats(user_id=tg_id)
        print(f"✅ get_user_storage_stats успешно: {stats}")
        
        return True

def check_database_state():
    """Проверка состояния базы данных"""
    print("\n📊 Проверка состояния базы данных...")
    
    with SessionLocal() as db:
        # Количество пользователей
        users_count = db.execute(select(User)).scalars().all()
        print(f"👥 Пользователей в базе: {len(users_count)}")
        
        # Количество генераций
        generations_count = db.execute(select(GenerationHistory)).scalars().all()
        print(f"🎬 Генераций в базе: {len(generations_count)}")
        
        # Последние генерации
        if generations_count:
            print("\n📋 Последние генерации:")
            for gen in generations_count[-3:]:  # Последние 3
                print(f"  - ID: {gen.id}, User ID: {gen.user_id}, Type: {gen.generation_type}")

if __name__ == "__main__":
    print("🚀 Запуск теста исправления user_storage.py")
    print("=" * 50)
    
    try:
        # Проверяем состояние базы данных
        check_database_state()
        
        # Тестируем исправления
        success = test_user_id_conversion()
        
        if success:
            print("\n🎉 Все тесты прошли успешно!")
            print("✅ Проблема с Foreign Key Violation исправлена")
        else:
            print("\n❌ Тесты не прошли")
            
    except Exception as e:
        print(f"\n💥 Ошибка во время тестирования: {e}")
        import traceback
        traceback.print_exc()
