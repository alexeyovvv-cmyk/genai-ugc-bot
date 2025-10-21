"""Migration script to add R2 fields to existing tables."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from tg_bot.db import engine

def run_migration():
    """Add R2 fields to existing tables."""
    print("🔄 Running R2 fields migration...")
    
    try:
        with engine.connect() as conn:
            # Check if columns already exist and add them one by one
            from sqlalchemy import inspect
            inspector = inspect(engine)
            
            # Get existing columns for assets table
            try:
                existing_columns = [col['name'] for col in inspector.get_columns('assets')]
            except:
                existing_columns = []
            
            # Add R2 fields to assets table if they don't exist
            columns_to_add = [
                ('r2_key', 'VARCHAR'),
                ('r2_url', 'VARCHAR'), 
                ('r2_url_expires_at', 'TIMESTAMP'),
                ('file_size', 'INTEGER'),
                ('version', 'INTEGER DEFAULT 1')
            ]
            
            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE assets ADD COLUMN {col_name} {col_type}"))
                        print(f"✅ Added column {col_name} to assets table")
                    except Exception as e:
                        print(f"⚠️ Could not add column {col_name}: {e}")
            
            # Create generation_history table
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS generation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                generation_type VARCHAR NOT NULL,
                r2_video_key VARCHAR,
                r2_audio_key VARCHAR,
                r2_image_key VARCHAR,
                character_gender VARCHAR,
                character_age VARCHAR,
                text_prompt VARCHAR,
                credits_spent INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
            
            # Create indexes
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_generation_history_user_id ON generation_history(user_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_generation_history_created_at ON generation_history(created_at)"))
            except Exception as e:
                print(f"⚠️ Could not create indexes: {e}")
            
            conn.commit()
            
            print("✅ R2 fields migration completed successfully")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()
