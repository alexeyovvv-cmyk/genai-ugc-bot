#!/usr/bin/env python3
"""
Скрипт для принудительного выполнения миграции
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tg_bot.db import engine
from sqlalchemy import text

def force_migration():
    """Принудительно выполняем миграцию"""
    print("🔄 Принудительное выполнение миграции")
    print("=" * 50)
    
    try:
        with engine.connect() as conn:
            # Выполняем миграцию
            migration_sql = """
            ALTER TABLE user_state 
            ADD COLUMN IF NOT EXISTS selected_character_idx INTEGER,
            ADD COLUMN IF NOT EXISTS character_text VARCHAR,
            ADD COLUMN IF NOT EXISTS situation_prompt VARCHAR,
            ADD COLUMN IF NOT EXISTS character_gender VARCHAR,
            ADD COLUMN IF NOT EXISTS character_age VARCHAR,
            ADD COLUMN IF NOT EXISTS character_page INTEGER DEFAULT 0;
            """
            
            print("📝 Выполняем миграцию...")
            conn.execute(text(migration_sql))
            conn.commit()
            print("✅ Миграция выполнена успешно!")
            
            # Проверяем результат
            print("\n🔍 Проверяем результат миграции...")
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'user_state' 
                AND column_name IN ('character_gender', 'character_age', 'character_page')
                ORDER BY column_name
            """)).fetchall()
            
            if result:
                print("✅ Новые колонки добавлены:")
                for row in result:
                    print(f"  - {row[0]}: {row[1]}")
            else:
                print("❌ Новые колонки не найдены")
                
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_migration()
