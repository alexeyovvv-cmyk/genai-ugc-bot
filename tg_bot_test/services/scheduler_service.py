# scheduler_service.py — сервис для планирования задач
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from tg_bot.utils.statistics import generate_statistics_report


async def send_daily_statistics(bot):
    """Отправляет ежедневную статистику в админский чат"""
    try:
        print("[SCHEDULER] Starting daily statistics generation...")
        
        admin_chat_id = int(os.getenv("TEST_ADMIN_FEEDBACK_CHAT_ID", "0"))
        if admin_chat_id == 0:
            print("[SCHEDULER] ERROR: ADMIN_FEEDBACK_CHAT_ID not set, skipping statistics")
            return
        
        print(f"[SCHEDULER] Admin chat ID: {admin_chat_id}")
        
        print("[SCHEDULER] Generating statistics report...")
        report = generate_statistics_report()
        print(f"[SCHEDULER] Report generated successfully (length: {len(report)} chars)")
        
        print("[SCHEDULER] Sending message to admin chat...")
        await bot.send_message(
            chat_id=admin_chat_id,
            text=report,
            parse_mode="HTML"
        )
        print(f"[SCHEDULER] ✅ Daily statistics sent successfully to admin chat {admin_chat_id}")
        
    except ValueError as ve:
        error_msg = f"[SCHEDULER] ❌ VALUE ERROR: Invalid ADMIN_FEEDBACK_CHAT_ID format: {ve}"
        print(error_msg)
        try:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=f"❌ <b>Ошибка конфигурации</b>\n\n{error_msg}",
                parse_mode="HTML"
            )
        except:
            print("[SCHEDULER] Could not send error message to admin chat")
    except Exception as e:
        error_msg = f"[SCHEDULER] ❌ CRITICAL ERROR in daily statistics: {type(e).__name__}: {str(e)}"
        print(error_msg)
        print(f"[SCHEDULER] Full traceback:")
        import traceback
        traceback.print_exc()
        
        # Пытаемся отправить сообщение об ошибке в админский чат
        try:
            admin_chat_id = int(os.getenv("TEST_ADMIN_FEEDBACK_CHAT_ID", "0"))
            if admin_chat_id != 0:
                error_report = f"""❌ <b>Ошибка при отправке ежедневной статистики</b>

🔍 <b>Тип ошибки:</b> {type(e).__name__}
📝 <b>Сообщение:</b> {str(e)}
🕐 <b>Время:</b> {os.getenv('TZ', 'UTC')}

📋 <b>Детали:</b>
<code>{traceback.format_exc()}</code>"""
                
                await bot.send_message(
                    chat_id=admin_chat_id,
                    text=error_report,
                    parse_mode="HTML"
                )
                print(f"[SCHEDULER] Error report sent to admin chat {admin_chat_id}")
        except Exception as send_error:
            print(f"[SCHEDULER] ❌ Failed to send error report: {send_error}")


def setup_scheduler(bot):
    """Инициализирует планировщик для отправки ежедневной статистики"""
    scheduler = AsyncIOScheduler()
    
    # Настраиваем отправку статистики каждый день в 19:00 по Москве
    scheduler.add_job(
        func=send_daily_statistics,
        args=[bot],
        trigger=CronTrigger(
            hour=19,
            minute=0,
            timezone=pytz.timezone('Europe/Moscow')
        ),
        id='daily_statistics',
        name='Daily Statistics Report',
        replace_existing=True,
        max_instances=1
    )
    
    # Запускаем планировщик
    scheduler.start()
    print("[SCHEDULER] Daily statistics scheduler started (19:00 MSK)")
    
    return scheduler
