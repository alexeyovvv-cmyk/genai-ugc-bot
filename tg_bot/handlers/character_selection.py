"""Character selection handlers for the Telegram bot.

This module contains handlers for:
- Character gender/age selection
- Character gallery navigation
- Character picking
"""

from aiogram import F
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from tg_bot.states import UGCCreation
from tg_bot.utils.credits import ensure_user
from tg_bot.utils.user_state import (
    set_character_gender, get_character_gender,
    set_character_age, get_character_age,
    set_character_page, get_character_page,
    set_voice_page, get_voice_page,
    set_selected_character, set_original_character_path
)
from tg_bot.utils.files import list_character_images, get_character_image
from tg_bot.keyboards import (
    gender_selection_menu, age_selection_menu,
    character_gallery_menu, character_edit_offer_menu
)
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "select_character")
async def select_character(c: CallbackQuery, state: FSMContext):
    """Начать процесс выбора персонажа - сначала выбор пола"""
    ensure_user(c.from_user.id)
    await c.message.edit_text(
        "👤 <b>Выбор персонажа</b>\n\n"
        "Сначала выбери пол персонажа:",
        parse_mode="HTML",
        reply_markup=gender_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_gender_selection)
    await c.answer()


@dp.callback_query(F.data == "gender_male")
async def gender_male_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал мужской пол"""
    ensure_user(c.from_user.id)
    set_character_gender(c.from_user.id, "male")
    logger.info(f"User {c.from_user.id} выбрал пол: мужской")
    
    await c.message.edit_text(
        "👨 <b>Мужской пол выбран</b>\n\n"
        "Теперь выбери возраст персонажа:",
        parse_mode="HTML",
        reply_markup=age_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_age_selection)
    await c.answer()


@dp.callback_query(F.data == "gender_female")
async def gender_female_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал женский пол"""
    ensure_user(c.from_user.id)
    set_character_gender(c.from_user.id, "female")
    logger.info(f"User {c.from_user.id} выбрал пол: женский")
    
    await c.message.edit_text(
        "👩 <b>Женский пол выбран</b>\n\n"
        "Теперь выбери возраст персонажа:",
        parse_mode="HTML",
        reply_markup=age_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_age_selection)
    await c.answer()


@dp.callback_query(F.data == "age_young")
async def age_young_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал молодой возраст"""
    ensure_user(c.from_user.id)
    set_character_age(c.from_user.id, "young")
    set_character_page(c.from_user.id, 0)  # Сбрасываем страницу
    logger.info(f"User {c.from_user.id} выбрал возраст: молодой")
    
    await show_character_gallery(c, state)


@dp.callback_query(F.data == "age_elderly")
async def age_elderly_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал пожилой возраст"""
    ensure_user(c.from_user.id)
    set_character_age(c.from_user.id, "elderly")
    set_character_page(c.from_user.id, 0)  # Сбрасываем страницу
    logger.info(f"User {c.from_user.id} выбрал возраст: пожилой")
    
    await show_character_gallery(c, state)


async def show_character_gallery(c: CallbackQuery, state: FSMContext):
    """Показать галерею персонажей"""
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    page = get_character_page(c.from_user.id)
    
    if not gender or not age:
        await c.message.answer(
            "❌ Ошибка: не выбраны параметры персонажа. Начните сначала.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Получаем изображения для текущей страницы
    images, has_next = list_character_images(gender, age, page, limit=5)
    
    if not images:
        await c.message.edit_text(
            f"❌ <b>Нет доступных персонажей</b>\n\n"
            f"Для выбранных параметров (пол: {gender}, возраст: {age}) "
            f"персонажи не найдены.\n\n"
            f"Попробуйте изменить параметры:",
            parse_mode="HTML",
            reply_markup=character_gallery_menu(page, has_next, len(images))
        )
        return await c.answer()
    
    # Отправляем изображения персонажей одним альбомом (до 5 в одной группе)
    media = []
    for idx, image_path in enumerate(images):
        global_index = page * 5 + idx
        caption = None
        
        # Проверяем, является ли путь R2 ключом или локальным путем
        if image_path.startswith('presets/'):
            # Это R2 ключ, нужно скачать файл или использовать presigned URL
            from tg_bot.utils.files import get_character_image_url
            from tg_bot.services.r2_service import download_file
            import tempfile
            import os
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_path = temp_file.name
            
            # Скачиваем файл из R2
            if download_file(image_path, temp_path):
                media.append(
                    InputMediaPhoto(
                        media=FSInputFile(temp_path),
                        caption=caption
                    )
                )
            else:
                logger.warning(f"Failed to download R2 file: {image_path}")
                continue
        else:
            # Это локальный путь
            media.append(
                InputMediaPhoto(
                    media=FSInputFile(image_path),
                    caption=caption
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
        f"👤 <b>Персонажи ({gender}, {age})</b>\n\n"
        f"Страница {page + 1}. Выбери персонажа:",
        parse_mode="HTML",
        reply_markup=character_gallery_menu(page, has_next, len(images))
    )
    
    await state.set_state(UGCCreation.waiting_character_gallery)
    await c.answer()


@dp.callback_query(F.data.startswith("char_page:"))
async def character_page_changed(c: CallbackQuery, state: FSMContext):
    """Пользователь переключил страницу персонажей"""
    ensure_user(c.from_user.id)
    page = int(c.data.split(":", 1)[1])
    set_character_page(c.from_user.id, page)
    logger.info(f"User {c.from_user.id} переключил на страницу {page}")
    
    await show_character_gallery(c, state)


@dp.callback_query(F.data.startswith("char_pick:"))
async def character_picked(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал конкретного персонажа"""
    ensure_user(c.from_user.id)
    idx = int(c.data.split(":", 1)[1])
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    
    # Получаем изображение персонажа
    character_image = get_character_image(gender, age, idx)
    
    if not character_image:
        await c.message.answer("❌ Персонаж не найден. Попробуйте выбрать другого.")
        return await c.answer()
    
    # Сохраняем выбор персонажа (используем глобальный индекс)
    set_selected_character(c.from_user.id, idx)
    set_voice_page(c.from_user.id, 0)  # Сбрасываем страницу голосов
    logger.info(f"User {c.from_user.id} выбрал персонажа #{idx+1} ({gender}, {age})")
    
    # Сохраняем оригинальный путь к изображению персонажа
    set_original_character_path(c.from_user.id, character_image)
    
    # Подтверждаем выбор пользователю: сообщение и изображение выбранного персонажа
    await c.message.answer(f"✅ Вы выбрали персонажа #{idx+1}")
    await c.message.answer_photo(FSInputFile(character_image))
    
    # Предлагаем редактирование персонажа
    await c.message.answer(
        "🎨 <b>Хотите отредактировать персонажа?</b>\n\n"
        "Вы можете изменить:\n"
        "• Фон (пляж, офис, улица)\n"
        "• Одежду (деловой стиль, casual)\n"
        "• Аксессуары (очки, шляпа)\n"
        "• И многое другое!",
        parse_mode="HTML",
        reply_markup=character_edit_offer_menu()
    )
    
    await state.set_state(UGCCreation.waiting_edit_decision)
    await c.answer()


@dp.callback_query(F.data == "back_to_character_gallery")
async def back_to_character_gallery(c: CallbackQuery, state: FSMContext):
    """Возврат к галерее персонажей из галереи голосов"""
    await show_character_gallery(c, state)


@dp.callback_query(F.data == "change_character_params")
async def change_character_params(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет изменить параметры персонажа"""
    await c.message.edit_text(
        "🔄 <b>Изменение параметров персонажа</b>\n\n"
        "Выбери пол персонажа:",
        parse_mode="HTML",
        reply_markup=gender_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_gender_selection)
    await c.answer()


@dp.callback_query(F.data == "back_to_gender")
async def back_to_gender(c: CallbackQuery, state: FSMContext):
    """Возврат к выбору пола"""
    await c.message.edit_text(
        "👤 <b>Выбор персонажа</b>\n\n"
        "Выбери пол персонажа:",
        parse_mode="HTML",
        reply_markup=gender_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_gender_selection)
    await c.answer()


@dp.callback_query(F.data == "back_to_age")
async def back_to_age(c: CallbackQuery, state: FSMContext):
    """Возврат к выбору возраста"""
    gender = get_character_gender(c.from_user.id)
    gender_text = "👨 Мужской" if gender == "male" else "👩 Женский"
    
    await c.message.edit_text(
        f"👤 <b>Выбор персонажа</b>\n\n"
        f"Пол: {gender_text}\n"
        f"Выбери возраст персонажа:",
        parse_mode="HTML",
        reply_markup=age_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_age_selection)
    await c.answer()
