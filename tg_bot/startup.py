"""Startup module for the Telegram bot.

This module contains all startup logic including:
- Database initialization
- Migrations
- R2 lifecycle configuration
- Statistics display
"""

from aiogram import Bot
from tg_bot.db import engine
from tg_bot.models import Base
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)


async def setup_startup(bot: Bot):
    """
    Setup bot startup logic.
    
    Args:
        bot: The aiogram Bot instance
    """
    # создаём таблицы
    logger.info("🔧 Creating database tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified successfully")
        
        # Run migration to add new columns if they don't exist
        logger.info("🔄 Running migrations for new columns...")
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                # Try to add new columns (will be skipped if already exist)
                migration_sql = """
                ALTER TABLE user_state 
                ADD COLUMN IF NOT EXISTS selected_character_idx INTEGER,
                ADD COLUMN IF NOT EXISTS character_text VARCHAR,
                ADD COLUMN IF NOT EXISTS character_gender VARCHAR,
                ADD COLUMN IF NOT EXISTS character_age VARCHAR,
                ADD COLUMN IF NOT EXISTS character_page INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS selected_voice_idx INTEGER,
                ADD COLUMN IF NOT EXISTS voice_page INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS original_character_path VARCHAR,
                ADD COLUMN IF NOT EXISTS edited_character_path VARCHAR,
                ADD COLUMN IF NOT EXISTS edit_iteration_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS video_format VARCHAR,
                ADD COLUMN IF NOT EXISTS background_video_path VARCHAR;
                
                -- Add user name fields to users table
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS first_name VARCHAR,
                ADD COLUMN IF NOT EXISTS last_name VARCHAR,
                ADD COLUMN IF NOT EXISTS username VARCHAR;
                
                -- Create user_activity table if it doesn't exist
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    last_activity_date VARCHAR NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id);

                -- Ensure users.tg_id can store large Telegram IDs
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'tg_id' AND udt_name = 'int4'
                    ) THEN
                        ALTER TABLE users
                        ALTER COLUMN tg_id TYPE BIGINT USING tg_id::bigint;
                    END IF;
                END$$;
                """
                conn.execute(text(migration_sql))
                conn.commit()
                logger.info("✅ Migrations completed successfully")
            except Exception as migration_error:
                logger.warning(f"Migration warning: {migration_error}")
                # Continue anyway - tables might already be up to date
        
        # Show table names
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"📊 Available tables: {', '.join(tables) if tables else 'none yet'}")
        
        # Show database stats
        from sqlalchemy import select
        from tg_bot.db import SessionLocal
        from tg_bot.models import User, CreditLog
        with SessionLocal() as db:
            user_count = len(db.execute(select(User)).scalars().all())
            credit_log_count = len(db.execute(select(CreditLog)).scalars().all())
            logger.info(f"[STARTUP] 👥 Users in database: {user_count}")
            logger.info(f"[STARTUP] 📊 Credit operations logged: {credit_log_count}")
            
            if user_count > 0:
                logger.info(f"[STARTUP] ✅ Database has {user_count} existing users - data persisted!")
                # Show user credits
                users = db.execute(select(User)).scalars().all()
                for user in users[:5]:  # Show first 5 users
                    logger.info(f"[STARTUP]   User {user.tg_id}: {user.credits} credits")
            else:
                logger.info(f"[STARTUP] ⚠️  Database is empty - first start or data was lost")
                
        # Show Telegram webhook status
        try:
            info = await bot.get_webhook_info()
            logger.info(f"🌐 Webhook info: url={info.url or 'None'}, has_custom_certificate={info.has_custom_certificate}, pending_update_count={info.pending_update_count}")
        except Exception as wh_err:
            logger.warning(f"Could not fetch webhook info: {wh_err}")
        
        # Configure R2 lifecycle for temp edits
        try:
            from tg_bot.services.r2_service import configure_temp_edits_lifecycle
            configure_temp_edits_lifecycle()
        except Exception as e:
            logger.warning(f"R2 lifecycle configuration skipped: {e}")

    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise
