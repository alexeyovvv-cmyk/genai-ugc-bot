# main.py — точка входа бота (упрощенная версия)
import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot

from tg_bot.config import BASE_DIR, DATABASE_URL, ensure_dirs
from tg_bot.startup import setup_startup
from tg_bot.handlers import register_all_handlers
from tg_bot.dispatcher import dp
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

load_dotenv()

# Check for required environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("=" * 80)
    logger.error("❌ ERROR: TELEGRAM_BOT_TOKEN not found in environment variables!")
    logger.error("=" * 80)
    logger.error("")
    logger.error("Please set the following environment variable in Railway:")
    logger.error("")
    logger.error("  TELEGRAM_BOT_TOKEN=your_bot_token_here")
    logger.error("")
    logger.error("Get your token from: https://t.me/BotFather")
    logger.error("")
    logger.error("See ENV_VARIABLES.md for full list of required variables.")
    logger.error("=" * 80)
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

logger.info(f"✅ Bot token found: {TELEGRAM_BOT_TOKEN[:10]}...")
ensure_dirs()
logger.info(f"✅ BASE_DIR resolved to: {BASE_DIR}")
logger.info(f"✅ DATABASE_URL: {DATABASE_URL}")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Initialize admin module
try:
    from tg_bot.admin import setup_admin
    setup_admin(dp, bot)
    logger.info("✅ Admin module initialized")
except Exception as e:
    logger.warning(f"Admin module not initialized: {e}")

# Initialize scheduler for daily statistics
try:
    from tg_bot.services.scheduler_service import setup_scheduler
    scheduler = setup_scheduler(bot)
    logger.info("✅ Statistics scheduler initialized")
except Exception as e:
    logger.warning(f"Statistics scheduler not initialized: {e}")

# FSM storage is already configured in dispatcher.py
# No additional setup needed

# Register all handlers
register_all_handlers(dp)

@dp.startup()
async def on_startup():
    """Bot startup handler"""
    await setup_startup(bot)

async def main():
    """Main function to run the bot"""
    # Detect if running in Railway/production (has PORT env var) or locally
    port = os.getenv("PORT")
    
    # Railway always sets PORT for web services
    if port:
        logger.info("🚀 Railway mode detected - using webhook")
        # Railway/Production mode: use webhook
        from aiohttp import web
        
        # Get webhook URL from environment variable
        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            logger.error("❌ WEBHOOK_URL environment variable not found")
            raise RuntimeError("WEBHOOK_URL environment variable is required")
        
        logger.info(f"Setting webhook to: {webhook_url}")
        
        try:
            # Ensure old webhook (if any) is removed first to avoid conflicts
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Deleted existing webhook (if any)")
        except Exception as e:
            logger.warning(f"Failed to delete existing webhook (continuing): {e}")

        try:
            await bot.set_webhook(webhook_url, drop_pending_updates=True)
            logger.info("Webhook set successfully!")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
        
        # Create aiohttp app
        app = web.Application()
        
        # Register dispatcher webhook handler
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        
        # Add health check endpoint
        async def health(request):
            return web.Response(text="OK")
        app.router.add_get("/health", health)
        app.router.add_get("/", health)
        
        setup_application(app, dp, bot=bot)
        
        # Run web server
        port_num = int(port)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=port_num)
        logger.info(f"Starting webhook server on port {port_num}")
        await site.start()
        
        # Keep running
        await asyncio.Event().wait()
    else:
        # No PORT found - this should not happen on Railway
        logger.error("❌ PORT environment variable not found. This bot requires Railway deployment.")
        raise RuntimeError("Bot must run on Railway platform")

if __name__ == "__main__":
    asyncio.run(main())
