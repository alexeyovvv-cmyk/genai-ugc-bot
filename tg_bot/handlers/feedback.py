"""Feedback handlers for the Telegram bot.

This module contains handlers for:
- Feedback form
- Feedback message handling
"""

import os
from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from tg_bot.states import Feedback
from tg_bot.keyboards import feedback_menu, back_to_main_menu
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "feedback")
async def show_feedback(c: CallbackQuery):
    """Show feedback form"""
    await c.message.edit_text(
        "✉️ <b>Обратная связь</b>\n\n"
        "Здесь вы можете оставить отзыв или вопрос.\n\n"
        "Нажмите кнопку ниже, чтобы написать сообщение, и мы получим его.",
        parse_mode="HTML",
        reply_markup=feedback_menu()
    )
    await c.answer()


@dp.callback_query(F.data == "feedback_write")
async def feedback_write(c: CallbackQuery, state: FSMContext):
    """Start feedback writing process"""
    await c.message.answer(
        "📝 Напишите сообщение обратной связи одним следующим сообщением.\n"
        "Мы получим его и ответим через бота.",
        reply_markup=back_to_main_menu()
    )
    await state.set_state(Feedback.waiting_message)
    await c.answer()


@dp.message(StateFilter(Feedback.waiting_message), F.chat.type == "private", F.text)
async def on_feedback_message(m: Message, state: FSMContext):
    """Handle feedback message from user"""
    ADMIN_FEEDBACK_CHAT_ID = int(os.getenv("ADMIN_FEEDBACK_CHAT_ID", "0"))
    if ADMIN_FEEDBACK_CHAT_ID == 0:
        return await m.answer("⚠️ Обратная связь временно недоступна.")
    
    user = m.from_user
    uname = f"@{user.username}" if user.username else "-"
    full = f"{user.first_name or ''} {user.last_name or ''}".strip()
    text_to_admin = (
        "📩 Новое обращение в поддержку\n"
        f"• From tg_id: {user.id}\n"
        f"• Имя: {full or '-'}\n"
        f"• Username: {uname}\n"
        "— — — — — — — — — —\n"
        f"{m.text}"
    )
    
    try:
        # Import bot instance from main
        from tg_bot.main import bot
        await bot.send_message(chat_id=ADMIN_FEEDBACK_CHAT_ID, text=text_to_admin)
        await m.answer("✅ Сообщение отправлено. Мы ответим через бота.")
    except Exception as e:
        logger.error(f"Failed to send feedback message: {e}")
        await m.answer("❌ Не удалось отправить сообщение администратору. Попробуйте позже.")
    
    await state.clear()
