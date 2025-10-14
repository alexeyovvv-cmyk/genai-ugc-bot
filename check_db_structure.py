#!/usr/bin/env python3
"""
Скрипт для проверки структуры базы данных
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tg_bot.db import engine
from sqlalchemy import text, inspect

def check_database_structure():
    """Проверяем структуру базы данных"""
    print("🔍 Проверка структуры базы данных")
    print("=" * 50)
    
    try:
        with engine.connect() as conn:
            # Проверяем существование таблиц
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            print(f"📊 Найденные таблицы: {tables}")
            
            # Проверяем структуру таблицы user_state
            if 'user_state' in tables:
                print("\n📋 Структура таблицы user_state:")
                columns = inspector.get_columns('user_state')
                for col in columns:
                    print(f"  - {col['name']}: {col['type']} (nullable: {col['nullable']})")
                
                # Проверяем, есть ли нужные колонки
                column_names = [col['name'] for col in columns]
                required_columns = ['character_gender', 'character_age', 'character_page']
                
                print(f"\n✅ Найденные колонки: {column_names}")
                print(f"🔍 Требуемые колонки: {required_columns}")
                
                missing_columns = [col for col in required_columns if col not in column_names]
                if missing_columns:
                    print(f"❌ Отсутствующие колонки: {missing_columns}")
                else:
                    print("✅ Все требуемые колонки присутствуют!")
            
            # Проверяем структуру таблицы users
            if 'users' in tables:
                print("\n📋 Структура таблицы users:")
                columns = inspector.get_columns('users')
                for col in columns:
                    print(f"  - {col['name']}: {col['type']} (nullable: {col['nullable']})")
            
            # Проверяем данные в таблицах
            print("\n📊 Данные в таблицах:")
            
            # Количество пользователей
            result = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()
            print(f"  👥 Пользователей: {result[0]}")
            
            # Количество записей в user_state
            result = conn.execute(text("SELECT COUNT(*) FROM user_state")).fetchone()
            print(f"  📝 Записей в user_state: {result[0]}")
            
            # Проверяем, есть ли записи с новыми полями
            if 'character_gender' in column_names:
                result = conn.execute(text("SELECT COUNT(*) FROM user_state WHERE character_gender IS NOT NULL")).fetchone()
                print(f"  👤 Записей с выбранным полом: {result[0]}")
            
            if 'character_age' in column_names:
                result = conn.execute(text("SELECT COUNT(*) FROM user_state WHERE character_age IS NOT NULL")).fetchone()
                print(f"  🎂 Записей с выбранным возрастом: {result[0]}")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database_structure()
