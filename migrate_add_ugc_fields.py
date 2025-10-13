#!/usr/bin/env python3
"""
Миграция для добавления полей UGC в таблицу user_state
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    exit(1)

print(f"🔧 Connecting to database...")
engine = create_engine(DATABASE_URL, echo=True)

migration_sql = """
-- Добавляем новые колонки для UGC рекламы
ALTER TABLE user_state 
ADD COLUMN IF NOT EXISTS selected_character_idx INTEGER,
ADD COLUMN IF NOT EXISTS character_text VARCHAR,
ADD COLUMN IF NOT EXISTS situation_prompt VARCHAR;
"""

try:
    with engine.connect() as conn:
        print("🔄 Running migration...")
        conn.execute(text(migration_sql))
        conn.commit()
        print("✅ Migration completed successfully!")
        
        # Проверяем, что колонки добавлены
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_state'
            ORDER BY ordinal_position;
        """))
        
        print("\n📊 Current columns in user_state table:")
        for row in result:
            print(f"  - {row[0]}")
            
except Exception as e:
    print(f"❌ Migration failed: {e}")
    exit(1)

