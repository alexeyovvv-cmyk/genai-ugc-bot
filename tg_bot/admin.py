import os
import time
import functools
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from tg_bot.utils.credits import get_credits, add_credits
from tg_bot.db import SessionLocal
from tg_bot.models import User, CreditLog
from tg_bot.utils.storage_stats import format_storage_summary, get_temp_file_stats
from tg_bot.services.r2_service import cleanup_temp_files, test_connection

# Create dispatcher instance
dp = Dispatcher()


ADMIN_TG_IDS = set(int(x) for x in os.getenv("ADMIN_TG_IDS", "").split(',') if x.strip())
RATE_LIMIT_WINDOW_SEC = int(os.getenv("ADMIN_RATE_LIMIT_WINDOW_SEC", "10"))
RATE_LIMIT_MAX_OPS = int(os.getenv("ADMIN_RATE_LIMIT_MAX_OPS", "5"))
ADMIN_FEEDBACK_CHAT_ID = int(os.getenv("ADMIN_FEEDBACK_CHAT_ID", "0"))

_admin_ops: dict[int, list[float]] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_TG_IDS


def ensure_private_not_forwarded(m: Message) -> bool:
    # Только личный чат
    if not m.chat or getattr(m.chat, "type", None) != "private":
        return False
    # Не доверять пересланным сообщениям/внешним источникам
    if getattr(m, "forward_date", None) or getattr(m, "forward_origin", None):
        return False
    return True


def rate_limited(func):
    @functools.wraps(func)
    async def wrapper(m: Message, *args, **kwargs):
        admin_id = m.from_user.id if m.from_user else 0
        now = time.time()
        bucket = _admin_ops.setdefault(admin_id, [])
        cutoff = now - RATE_LIMIT_WINDOW_SEC
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= RATE_LIMIT_MAX_OPS:
            await m.answer("⏱ Слишком много операций. Попробуйте позже.")
            return
        bucket.append(now)
        return await func(m, *args, **kwargs)
    return wrapper


def parse_args(text: str) -> list[str]:
    parts = (text or "").split()
    return parts[1:] if len(parts) > 1 else []


def setup_admin(dp, bot_instance):
    @dp.message(Command("credit_get"))
    @rate_limited
    async def credit_get(m: Message):
        if not (m.from_user and is_admin(m.from_user.id) and ensure_private_not_forwarded(m)):
            return
        args = parse_args(m.text)
        if len(args) < 1 or not args[0].isdigit():
            return await m.answer("Использование: /credit_get <tg_id>")
        tg_id = int(args[0])
        bal = get_credits(tg_id)
        # последние 5 операций
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.tg_id == tg_id))
            logs = []
            if user:
                logs = db.execute(
                    select(CreditLog)
                    .where(CreditLog.user_id == user.id)
                    .order_by(CreditLog.created_at.desc())
                    .limit(5)
                ).scalars().all()
        history = "\n".join([
            f"{'+' if l.delta>0 else ''}{l.delta} | {l.reason} | {l.created_at}" for l in logs
        ]) if logs else "нет"
        await m.answer(f"Баланс: {bal}\nПоследние операции:\n{history}")

    @dp.message(Command("credit_add"))
    @rate_limited
    async def credit_add_cmd(m: Message):
        if not (m.from_user and is_admin(m.from_user.id) and ensure_private_not_forwarded(m)):
            return
        args = parse_args(m.text)
        if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
            return await m.answer("Использование: /credit_add <tg_id> <amount> [reason]")
        tg_id = int(args[0]); amount = int(args[1]); reason = "admin_add"
        if len(args) >= 3:
            reason = " ".join(args[2:])[:100]
        add_credits(tg_id, amount, reason)
        await m.answer(f"OK: +{amount} кредитов для {tg_id} (reason={reason})")


    @dp.message(Command("credit_history"))
    @rate_limited
    async def credit_history_cmd(m: Message):
        if not (m.from_user and is_admin(m.from_user.id) and ensure_private_not_forwarded(m)):
            return
        args = parse_args(m.text)
        if len(args) < 1 or not args[0].isdigit():
            return await m.answer("Использование: /credit_history <tg_id> [limit]")
        tg_id = int(args[0])
        limit = int(args[1]) if len(args) >= 2 and args[1].isdigit() else 10
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.tg_id == tg_id))
            if not user:
                return await m.answer("Пользователь не найден")
            logs = db.execute(
                select(CreditLog)
                .where(CreditLog.user_id == user.id)
                .order_by(CreditLog.created_at.desc())
                .limit(limit)
            ).scalars().all()
        if not logs:
            return await m.answer("История пуста")
        lines = [f"{'+' if l.delta>0 else ''}{l.delta} | {l.reason} | {l.created_at}" for l in logs]
        await m.answer("Последние операции:\n" + "\n".join(lines))

    @dp.message(Command("reply"))
    @rate_limited
    async def admin_reply(m: Message):
        # Проверяем, что сообщение из ADMIN_FEEDBACK_CHAT_ID
        if str(m.chat.id) != str(ADMIN_FEEDBACK_CHAT_ID):
            return
        
        # Проверяем, что отправитель в списке админов
        if not (m.from_user and is_admin(m.from_user.id)):
            return
        
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit():
            return await m.answer("Использование: /reply <tg_id> <text>")
        
        target_id = int(parts[1])
        reply_text = parts[2]
        
        try:
            await bot_instance.send_message(chat_id=target_id, text=f"🛠 Ответ поддержки:\n{reply_text}")
            await m.answer("✅ Ответ отправлен.")
        except Exception as e:
            import traceback
            error_details = f"{type(e).__name__}: {str(e)}"
            await m.answer(f"❌ Не удалось доставить сообщение пользователю.\n\nОшибка: {error_details}")
            print(f"[ADMIN_REPLY] Error sending message to {target_id}: {error_details}")
            traceback.print_exc()

    @dp.message(Command("stats"))
    @rate_limited
    async def stats_command(m: Message):
        print(f"[ADMIN_STATS] Stats command received from user {m.from_user.id if m.from_user else 'unknown'}")
        print(f"[ADMIN_STATS] Chat ID: {m.chat.id}, Expected: {ADMIN_FEEDBACK_CHAT_ID}")
        
        # Проверяем, что сообщение из ADMIN_FEEDBACK_CHAT_ID
        if str(m.chat.id) != str(ADMIN_FEEDBACK_CHAT_ID):
            print(f"[ADMIN_STATS] ❌ REJECTED: Message not from admin feedback chat")
            return
        
        # Проверяем, что отправитель в списке админов
        if not (m.from_user and is_admin(m.from_user.id)):
            print(f"[ADMIN_STATS] ❌ REJECTED: User {m.from_user.id if m.from_user else 'unknown'} is not admin")
            return
        
        print(f"[ADMIN_STATS] ✅ User {m.from_user.id} is authorized, generating statistics...")
        
        try:
            print("[ADMIN_STATS] Importing statistics module...")
            from tg_bot.utils.statistics import generate_statistics_report
            
            print("[ADMIN_STATS] Generating statistics report...")
            report = generate_statistics_report()
            print(f"[ADMIN_STATS] Report generated successfully (length: {len(report)} chars)")
            
            print("[ADMIN_STATS] Sending report to admin...")
            await m.answer(report, parse_mode="HTML")
            print(f"[ADMIN_STATS] ✅ Statistics report sent successfully to admin {m.from_user.id}")
            
        except ImportError as ie:
            error_msg = f"[ADMIN_STATS] ❌ IMPORT ERROR: Could not import statistics module: {ie}"
            print(error_msg)
            await m.answer(
                f"❌ <b>Ошибка импорта модуля статистики</b>\n\n"
                f"🔍 <b>Тип ошибки:</b> ImportError\n"
                f"📝 <b>Сообщение:</b> {str(ie)}\n\n"
                f"💡 <b>Решение:</b> Проверьте, что файл tg_bot/utils/statistics.py существует и не содержит синтаксических ошибок.",
                parse_mode="HTML"
            )
        except Exception as e:
            error_msg = f"[ADMIN_STATS] ❌ CRITICAL ERROR: {type(e).__name__}: {str(e)}"
            print(error_msg)
            print(f"[ADMIN_STATS] Full traceback:")
            import traceback
            traceback.print_exc()
            
            # Отправляем детальный отчет об ошибке
            error_report = f"""❌ <b>Ошибка при получении статистики</b>

🔍 <b>Тип ошибки:</b> {type(e).__name__}
📝 <b>Сообщение:</b> {str(e)}
👤 <b>Админ:</b> {m.from_user.id if m.from_user else 'unknown'}
🕐 <b>Время:</b> {os.getenv('TZ', 'UTC')}

📋 <b>Детали ошибки:</b>
<code>{traceback.format_exc()}</code>

💡 <b>Возможные причины:</b>
• Проблемы с подключением к базе данных
• Ошибки в SQL запросах
• Проблемы с часовыми поясами
• Отсутствующие зависимости"""
            
            await m.answer(error_report, parse_mode="HTML")

@dp.message(Command("storage"))
async def admin_storage(m: Message):
    """Показать статистику R2 хранилища"""
    if not is_admin(m.from_user.id):
        await m.answer("❌ У вас нет прав администратора")
        return
    
    try:
        summary = format_storage_summary()
        await m.answer(summary, parse_mode="Markdown")
    except Exception as e:
        await m.answer(f"❌ Ошибка при получении статистики хранилища: {e}")

@dp.message(Command("cleanup_temp"))
async def admin_cleanup_temp(m: Message):
    """Очистить временные файлы вручную"""
    if not is_admin(m.from_user.id):
        await m.answer("❌ У вас нет прав администратора")
        return
    
    try:
        # Get stats before cleanup
        temp_stats_before = get_temp_file_stats()
        
        # Run cleanup
        cleanup_stats = cleanup_temp_files()
        
        # Format response
        response = f"""🧹 **Очистка временных файлов**

**До очистки:**
• Файлов: {temp_stats_before.get('total_files', 0):,}
• Размер: {temp_stats_before.get('total_size_mb', 0):.2f} MB

**Результат очистки:**
• Удалено файлов: {cleanup_stats['deleted_files']}
• Освобождено места: {cleanup_stats['deleted_size_mb']:.2f} MB

✅ Очистка завершена"""
        
        await m.answer(response, parse_mode="Markdown")
    except Exception as e:
        await m.answer(f"❌ Ошибка при очистке временных файлов: {e}")

@dp.message(Command("r2_test"))
async def admin_r2_test(m: Message):
    """Тест подключения к R2"""
    if not is_admin(m.from_user.id):
        await m.answer("❌ У вас нет прав администратора")
        return
    
    try:
        if test_connection():
            await m.answer("✅ Подключение к R2 успешно")
        else:
            await m.answer("❌ Ошибка подключения к R2")
    except Exception as e:
        await m.answer(f"❌ Ошибка тестирования R2: {e}")

@dp.message(Command("webhook_reset"))
async def admin_webhook_reset(m: Message):
    """Принудительно сбросить webhook"""
    if not is_admin(m.from_user.id):
        await m.answer("❌ У вас нет прав администратора")
        return
    
    try:
        # Delete current webhook
        await bot_instance.delete_webhook(drop_pending_updates=True)
        await m.answer("✅ Webhook удален. Ожидайте 2 секунды...")
        
        import asyncio
        await asyncio.sleep(2)
        
        # Get webhook URL from environment
        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            await m.answer("❌ WEBHOOK_URL не найден в переменных окружения")
            return
        
        # Set new webhook
        await bot_instance.set_webhook(webhook_url, drop_pending_updates=True)
        
        # Verify webhook
        webhook_info = await bot_instance.get_webhook_info()
        
        await m.answer(
            f"✅ Webhook успешно сброшен!\n\n"
            f"🔗 URL: {webhook_info.url}\n"
            f"📊 Pending updates: {webhook_info.pending_update_count}\n"
            f"🕐 Last error: {webhook_info.last_error_date or 'Нет'}"
        )
        
    except Exception as e:
        await m.answer(f"❌ Ошибка при сбросе webhook: {e}")

