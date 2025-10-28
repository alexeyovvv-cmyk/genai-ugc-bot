"""Navigation handlers for the Telegram bot.

This module contains handlers for:
- Back navigation
- Main menu navigation
- UGC creation flow navigation
"""

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from tg_bot.utils.credits import get_credits
from tg_bot.keyboards import (
    main_menu, ugc_start_menu, back_to_main_menu
)
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(c: CallbackQuery, state: FSMContext):
    """Return to main menu"""
    current_credits = get_credits(c.from_user.id)
    await c.message.edit_text(
        "🎬 <b>Добро пожаловать в сервис Datanauts.co</b>\n\n"
        "Создавайте десятки UGC-like рекламных роликов за считанные минуты с помощью ИИ.\n"
        f"У тебя сейчас: <b>{current_credits} кредитов</b>. 1 сгенерированное видео = 1 кредит\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await state.clear()
    await c.answer()


@dp.callback_query(F.data == "back_previous")
async def back_previous(c: CallbackQuery):
    """Return to previous menu"""
    current_credits = get_credits(c.from_user.id)
    await c.message.edit_text(
       "🎬 <b>Добро пожаловать в сервис Datanauts.co</b>\n\n"
        "Создавайте десятки UGC-like рекламных роликов за считанные минуты с помощью ИИ.\n"
        f"У тебя сейчас: <b>{current_credits} кредитов</b>. 1 сгенерированное видео = 1 кредит\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await c.answer()


@dp.callback_query(F.data == "back_to_ugc")
async def back_to_ugc(c: CallbackQuery, state: FSMContext):
    """Return to UGC creation menu"""
    await c.message.edit_text(
        "🎬 <b>Создание UGC рекламы</b>\n\n"
        "Выбери один из вариантов:",
        parse_mode="HTML",
        reply_markup=ugc_start_menu()
    )
    await state.clear()
    await c.answer()


@dp.callback_query(F.data == "create_ugc")
async def start_ugc_creation(c: CallbackQuery, state: FSMContext):
    """Start UGC creation process - redirect to format selection"""
    from tg_bot.handlers.format_selection import show_format_selection
    await show_format_selection(c, state)


@dp.callback_query(F.data == "create_character")
async def create_character(c: CallbackQuery):
    """Handle create character option (not implemented yet)"""
    await c.message.answer(
        "✨ <b>Создание персонажа</b>\n\n"
        "Эта функция пока недоступна, но скоро появится! 🚀\n\n"
        "Используй пока готовых персонажей.",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    await c.answer()


@dp.message(Command("main"))
async def open_main_menu(m: Message, state: FSMContext):
    """Handle /main command"""
    await state.clear()
    current_credits = get_credits(m.from_user.id)
    await m.answer(
       "🎬 <b>Добро пожаловать в сервис Datanauts.co</b>\n\n"
        "Создавайте десятки UGC-like рекламных роликов за считанные минуты с помощью ИИ.\n"
        f"У тебя сейчас: <b>{current_credits} кредитов</b>. 1 сгенерированное видео = 1 кредит\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@dp.message(Command("create_ads"))
async def open_create_ads(m: Message, state: FSMContext):
    """Handle /create_ads command"""
    await state.clear()
    await m.answer(
        "🎬 <b>Создание UGC рекламы</b>\n\n"
        "Выбери один из вариантов:",
        parse_mode="HTML",
        reply_markup=ugc_start_menu()
    )


@dp.message(Command("create"))
async def open_create(m: Message, state: FSMContext):
    """Handle /create command - redirect to format selection"""
    from tg_bot.utils.credits import ensure_user
    ensure_user(
        m.from_user.id,
        first_name=m.from_user.first_name,
        last_name=m.from_user.last_name,
        username=m.from_user.username
    )
    await state.clear()
    
    from tg_bot.handlers.format_selection import send_format_examples
    from tg_bot.keyboards import format_selection_menu
    from tg_bot.states import UGCCreation
    
    # Сначала отправляем примеры видео
    try:
        await send_format_examples(m)
    except Exception as e:
        logger.error(f"Failed to send format examples: {e}")
    
    # Сразу после примеров отправляем сообщение с кнопками выбора
    await m.answer(
        "☝️ Выберите формат:",
        parse_mode="HTML",
        reply_markup=format_selection_menu()
    )
    
    # Устанавливаем состояние
    await state.set_state(UGCCreation.waiting_format_selection)
