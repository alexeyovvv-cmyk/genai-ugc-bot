"""Start handlers for the Telegram bot.

This module contains handlers for:
- /start command
- FAQ
- User profile
"""

from aiogram import F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from tg_bot.utils.credits import get_credits
from tg_bot.utils.statistics import track_user_activity
from tg_bot.keyboards import main_menu, back_to_main_menu, bottom_navigation_menu
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

# Import shared dispatcher
from tg_bot.dispatcher import dp


@dp.message(CommandStart)
async def cmd_start(m: Message):
    """Handle /start command"""
    from tg_bot.utils.credits import ensure_user
    ensure_user(m.from_user.id)
    # track_user_activity(m.from_user.id)  # Отслеживаем активность пользователя - ОТКЛЮЧЕНО
    current_credits = get_credits(m.from_user.id)
    await m.answer(
        "🎬 <b>Добро пожаловать в сервис Datanauts.co</b>\n\n"
        "Создавайте десятки UGC-like рекламных роликов за считанные минуты с помощью ИИ.\n"
        f"У тебя сейчас: <b>{current_credits} кредитов</b>. 1 сгенерированное видео = 1 кредит\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )




@dp.callback_query(F.data == "faq")
async def show_faq(c: CallbackQuery):
    """Show FAQ"""
    from tg_bot.utils.constants import COST_UGC_VIDEO, DEFAULT_CREDITS
    
    faq_text = f"""
❓ <b>Как пользоваться ботом</b>

1️⃣ <b>Создать UGC рекламу</b>
   • Выберите персонажа из десятков готовых вариантов
   • Напишите текст, который должен озвучить персонаж
   • Получите готовый ролик для вашей UGC-like кампании за считанные минуты!

2️⃣ <b>Стоимость</b>
   • Генерация видео: {COST_UGC_VIDEO} кредит
   • При регистрации: 😎 welcome bonus {DEFAULT_CREDITS} бесплатных кредита

3️⃣ <b>Технические детали</b>
   • Видео генерируется с помощью лучших ИИ моделей
   • Формат видео: 9:16 (вертикальное)
   • Длительность: до 15 секунд

Если возникли вопросы — пиши в поддержку!
"""
    await c.message.answer(faq_text, parse_mode="HTML", reply_markup=back_to_main_menu())
    await c.answer()


@dp.callback_query(F.data == "profile")
async def show_profile(c: CallbackQuery):
    """Show user profile"""
    credits = get_credits(c.from_user.id)
    await c.message.edit_text(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: {c.from_user.id}\n"
        f"👤 Имя: {c.from_user.first_name or 'Не указано'}\n"
        f"💰 Кредиты: {credits}\n"
        f"📅 Статус: Активен\n\n"
        f"🎬 <b>Активность:</b>\n"
        f"• Создано видео: 0\n"
        f"• Последняя активность: сейчас\n\n"
        f"💡 <b>Совет:</b> Регулярно создавайте контент для лучших результатов!",
        parse_mode="HTML",
        reply_markup=bottom_navigation_menu()
    )
    await c.answer()
