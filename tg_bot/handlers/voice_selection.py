"""Voice selection handlers for the Telegram bot.

This module contains handlers for:
- Voice gallery navigation
- Voice selection
- Voice changing
"""

from aiogram import F
from aiogram.types import CallbackQuery, FSInputFile, InputMediaAudio
from aiogram.fsm.context import FSMContext

from tg_bot.states import UGCCreation
from tg_bot.utils.user_state import (
    get_character_gender, get_character_age,
    get_voice_page, set_voice_page,
    get_character_text, get_selected_voice,
    set_selected_voice
)
from tg_bot.utils.voices import list_voice_samples, get_voice_sample
from tg_bot.keyboards import voice_gallery_menu, back_to_main_menu
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


async def show_voice_gallery(c: CallbackQuery, state: FSMContext):
    """Показать галерею голосов для выбранного персонажа"""
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    page = get_voice_page(c.from_user.id)
    
    if not gender or not age:
        await c.message.answer(
            "❌ Ошибка: не выбраны параметры персонажа. Начните сначала.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Получаем голоса для текущей страницы
    voices, has_next = list_voice_samples(gender, age, page, limit=5)
    
    if not voices:
        await c.message.edit_text(
            f"❌ <b>Нет доступных голосов</b>\n\n"
            f"Для выбранной категории персонажа (пол: {gender}, возраст: {age}) "
            f"голоса не найдены.\n\n"
            f"Попробуйте изменить параметры персонажа:",
            parse_mode="HTML",
            reply_markup=voice_gallery_menu(page, has_next, len(voices))
        )
        return await c.answer()
    
    # Отправляем аудио-сэмплы голосов одним альбомом (до 5 в одной группе)
    media = []
    for idx, (name, voice_id, audio_path) in enumerate(voices):
        global_index = page * 5 + idx
        
        # Проверяем, является ли путь R2 ключом или локальным путем
        if audio_path.startswith('presets/'):
            # Это R2 ключ, нужно скачать файл или использовать presigned URL
            from tg_bot.services.r2_service import download_file
            import tempfile
            import os
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_path = temp_file.name
            
            # Скачиваем файл из R2
            if download_file(audio_path, temp_path):
                media.append(
                    InputMediaAudio(
                        media=FSInputFile(temp_path)
                    )
                )
            else:
                logger.warning(f"Failed to download R2 file: {audio_path}")
                continue
        else:
            # Это локальный путь
            media.append(
                InputMediaAudio(
                    media=FSInputFile(audio_path)
                )
            )
    
    if media:
        await c.message.answer_media_group(media)
        
        # Очищаем временные файлы
        for item in media:
            if hasattr(item.media, 'path') and item.media.path.startswith('/tmp'):
                try:
                    os.unlink(item.media.path)
                except:
                    pass
    
    # Отправляем меню с навигацией
    await c.message.answer(
        f"🎤 <b>Голоса для персонажа ({gender}, {age})</b>\n\n"
        f"Страница {page + 1}. Выбери голос для озвучки:",
        parse_mode="HTML",
        reply_markup=voice_gallery_menu(page, has_next, len(voices))
    )
    
    await state.set_state(UGCCreation.waiting_voice_gallery)
    await c.answer()


@dp.callback_query(F.data.startswith("voice_page:"))
async def voice_page_changed(c: CallbackQuery, state: FSMContext):
    """Пользователь переключил страницу голосов"""
    page = int(c.data.split(":", 1)[1])
    set_voice_page(c.from_user.id, page)
    logger.info(f"User {c.from_user.id} переключил на страницу голосов {page}")
    
    await show_voice_gallery(c, state)


@dp.callback_query(F.data.startswith("voice_pick:"))
async def voice_picked(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал конкретный голос"""
    from tg_bot.utils.credits import ensure_user
    ensure_user(c.from_user.id)
    idx = int(c.data.split(":", 1)[1])
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    
    if not gender or not age:
        await c.message.answer(
            "❌ Ошибка: не выбраны параметры персонажа. Начните сначала.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Получаем голос по индексу с учетом категории
    voice_data = get_voice_sample(gender, age, idx)
    
    if not voice_data:
        await c.message.answer("❌ Голос не найден. Попробуйте выбрать другой.")
        return await c.answer()
    
    name, voice_id, sample_path = voice_data
    
    # Сохраняем выбор голоса (используем глобальный индекс)
    set_selected_voice(c.from_user.id, voice_id)
    logger.info(f"User {c.from_user.id} выбрал голос #{idx+1}: {name} ({voice_id})")
    
    # Переходим к запросу текста
    await c.message.answer(
        f"✅ Отлично! Выбран голос #{idx+1}: {name}\n\n"
        "📝 Теперь напиши текст, который должен сказать персонаж.\n\n"
        "💡 Рекомендация: ставь точку или другой знак в конце предложения — так речь звучит естественнее.\n\n"
        "⚠️ <b>Важно:</b> Текст должен быть таким, чтобы озвучка заняла не более 15 секунд!\n\n"
        "Например: 'Привет! Попробуй наш новый продукт со скидкой 20%!'",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    
    await state.set_state(UGCCreation.waiting_character_text)
    await c.answer()


@dp.callback_query(F.data == "change_voice")
async def change_voice(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет выбрать другой голос"""
    # Получаем сохраненный текст персонажа
    character_text = get_character_text(c.from_user.id)
    
    if not character_text:
        await c.message.answer(
            "❌ Не найден текст персонажа. Попробуй начать сначала.",
            reply_markup=back_to_main_menu()
        )
        await state.clear()
        return await c.answer()
    
    # Проверяем, что параметры персонажа выбраны
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    
    if not gender or not age:
        await c.message.answer(
            "❌ Не выбраны параметры персонажа. Начните сначала.",
            reply_markup=back_to_main_menu()
        )
        await state.clear()
        return await c.answer()
    
    # Сбрасываем страницу голосов и показываем галерею
    set_voice_page(c.from_user.id, 0)
    await show_voice_gallery(c, state)
