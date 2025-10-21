"""Credits handlers for the Telegram bot.

This module contains handlers for:
- Credits balance display
- Top-up requests
- Credits history
"""

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from tg_bot.utils.credits import get_credits
from tg_bot.utils.constants import COST_UGC_VIDEO
from tg_bot.keyboards import credits_menu, back_to_main_menu
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "credits")
async def show_credits(c: CallbackQuery):
    """Show user's credits balance and history"""
    from sqlalchemy import select
    from tg_bot.db import SessionLocal
    from tg_bot.models import User, CreditLog
    
    cts = get_credits(c.from_user.id)
    
    # Получаем последние 5 операций с кредитами
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == c.from_user.id))
        if user:
            logs = db.execute(
                select(CreditLog)
                .where(CreditLog.user_id == user.id)
                .order_by(CreditLog.created_at.desc())
                .limit(5)
            ).scalars().all()
        else:
            logs = []
    
    # Формируем сообщение с историей
    history_text = ""
    if logs:
        history_text = "\n\n📊 <b>Последние операции:</b>\n"
        for log in logs:
            sign = "+" if log.delta > 0 else ""
            emoji = "📈" if log.delta > 0 else "📉"
            reason_map = {
                "signup_bonus": "Бонус при регистрации",
                "ugc_video_creation": "Генерация UGC видео",
                "refund_ugc_fail": "Возврат (ошибка)",
                "admin_add": "Начислено администратором"
            }
            reason_text = reason_map.get(log.reason, log.reason)
            history_text += f"{emoji} {sign}{log.delta} — {reason_text}\n"
    
    await c.message.answer(
        f"💰 <b>Баланс кредитов</b>\n\n"
        f"У тебя сейчас: <b>{cts} кредитов</b>\n\n"
        f"💡 <b>Стоимость услуг:</b>\n"
        f"• Генерация UGC видео: {COST_UGC_VIDEO} кредит"
        f"{history_text}",
        parse_mode="HTML",
        reply_markup=credits_menu()
    )
    await c.answer()


@dp.callback_query(F.data == "topup_request")
async def topup_request(c: CallbackQuery):
    """Handle top-up request"""
    await c.message.answer(
        (
            "Чтобы пополнить счёт, свяжитесь с администратором.\n\n"
            f"Ваш Telegram ID: <b>{c.from_user.id}</b>\n"
            "Передайте этот ID администратору для пополнения."
        ),
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    await c.answer()


@dp.message(Command("credits"))
async def open_credits(m: Message):
    """Handle /credits command"""
    from sqlalchemy import select
    from tg_bot.db import SessionLocal
    from tg_bot.models import User, CreditLog
    
    cts = get_credits(m.from_user.id)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == m.from_user.id))
        if user:
            logs = db.execute(
                select(CreditLog)
                .where(CreditLog.user_id == user.id)
                .order_by(CreditLog.created_at.desc())
                .limit(5)
            ).scalars().all()
        else:
            logs = []
    
    history_text = ""
    if logs:
        history_text = "\n\n📊 <b>Последние операции:</b>\n"
        for log in logs:
            sign = "+" if log.delta > 0 else ""
            emoji = "📈" if log.delta > 0 else "📉"
            reason_map = {
                "signup_bonus": "Бонус при регистрации",
                "ugc_video_creation": "Генерация UGC видео",
                "refund_ugc_fail": "Возврат (ошибка)",
                "admin_add": "Начислено администратором"
            }
            reason_text = reason_map.get(log.reason, log.reason)
            history_text += f"{emoji} {sign}{log.delta} — {reason_text}\n"
    
    await m.answer(
        f"💰 <b>Баланс кредитов</b>\n\n"
        f"У тебя сейчас: <b>{cts} кредитов</b>\n\n"
        f"💡 <b>Стоимость услуг:</b>\n"
        f"• Генерация UGC видео: {COST_UGC_VIDEO} кредит"
        f"{history_text}",
        parse_mode="HTML",
        reply_markup=credits_menu()
    )
