"""Format selection handlers for the Telegram bot.

This module contains handlers for:
- Video format selection (talking head / character with background)
- Background video upload and validation
- Sending format examples from R2
"""

import os
import time
from aiogram import F
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaVideo
from aiogram.fsm.context import FSMContext

from tg_bot.states import UGCCreation
from tg_bot.utils.credits import ensure_user
from tg_bot.utils.user_state import set_video_format, set_background_video_path
from tg_bot.keyboards import format_selection_menu, back_to_main_menu
from tg_bot.services.r2_service import download_file, upload_file, get_presigned_url
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)

# Пути к примерам форматов на R2
EXAMPLE_TALKING_HEAD_KEY = "examples/talking_head.mp4"
EXAMPLE_CHARACTER_BACKGROUND_KEY = "examples/character_with_background.mp4"


async def show_format_selection(c: CallbackQuery, state: FSMContext):
    """
    Показать экран выбора формата видео и отправить примеры.
    Вызывается при старте создания UGC.
    """
    ensure_user(
        c.from_user.id,
        first_name=c.from_user.first_name,
        last_name=c.from_user.last_name,
        username=c.from_user.username
    )
    
    # Сначала удаляем старое сообщение (чтобы не мешало)
    await c.message.delete()
    
    # Отправляем примеры видео и дожидаемся их отправки
    try:
        await send_format_examples(c.message)
    except Exception as e:
        logger.error(f"Failed to send format examples: {e}")
    
    # После того как видео отправлены, отправляем сообщение с кнопками выбора
    await c.message.answer(
        "☝️ Выберите формат:",
        parse_mode="HTML",
        reply_markup=format_selection_menu()
    )
    
    # Устанавливаем состояние ожидания выбора формата
    await state.set_state(UGCCreation.waiting_format_selection)
    await c.answer()


async def send_format_examples(message):
    """Отправить примеры форматов видео из R2 как media group (компактно)"""
    try:
        # Получаем presigned URLs для прямой отправки
        talking_head_url = get_presigned_url(EXAMPLE_TALKING_HEAD_KEY, expiry_hours=1)
        character_bg_url = get_presigned_url(EXAMPLE_CHARACTER_BACKGROUND_KEY, expiry_hours=1)
        
        if talking_head_url and character_bg_url:
            # Отправляем как media group (альбом) - будет компактнее
            media = [
                InputMediaVideo(
                    media=talking_head_url,
                    caption=(
                        "🎬 <b>Выберите формат для вашей UGC рекламы:</b>\n\n"
                        "1️⃣ <b>Говорящая голова</b> - классический формат с персонажем\n\n"
                        "2️⃣ <b>Персонаж с бекграундом</b> - персонаж на фоне вашего видео"
                    ),
                    parse_mode="HTML"
                ),
                InputMediaVideo(
                    media=character_bg_url,
                    parse_mode="HTML"
                )
            ]
            await message.answer_media_group(media)
            logger.info("Format examples sent as media group via presigned URLs")
            return
    except Exception as e:
        logger.warning(f"Failed to send examples via URLs: {e}, trying download method")
    
    # Fallback: скачиваем и отправляем локально как media group
    temp_dir = "temp_downloads"
    os.makedirs(temp_dir, exist_ok=True)
    
    talking_head_path = os.path.join(temp_dir, "example_talking_head.mp4")
    character_bg_path = os.path.join(temp_dir, "example_character_bg.mp4")
    
    try:
        # Скачиваем примеры из R2
        talking_head_downloaded = download_file(EXAMPLE_TALKING_HEAD_KEY, talking_head_path)
        character_bg_downloaded = download_file(EXAMPLE_CHARACTER_BACKGROUND_KEY, character_bg_path)
        
        if talking_head_downloaded and character_bg_downloaded:
            # Отправляем как media group
            media = [
                InputMediaVideo(
                    media=FSInputFile(talking_head_path),
                    caption=(
                        "🎬 <b>Выберите формат для вашей UGC рекламы:</b>\n\n"
                        "1️⃣ <b>Говорящая голова</b> - классический формат с персонажем\n\n"
                        "2️⃣ <b>Персонаж с бекграундом</b> - персонаж на фоне вашего видео"
                    ),
                    parse_mode="HTML"
                ),
                InputMediaVideo(
                    media=FSInputFile(character_bg_path),
                    parse_mode="HTML"
                )
            ]
            await message.answer_media_group(media)
            logger.info("Format examples sent as media group via download method")
            
            # Удаляем временные файлы
            os.remove(talking_head_path)
            os.remove(character_bg_path)
        else:
            logger.error("Failed to download one or both example videos")
    except Exception as e:
        logger.error(f"Failed to send format examples via download: {e}")


@dp.callback_query(F.data == "format_talking_head")
async def format_talking_head_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал формат 'Говорящая голова'"""
    logger.info(f"User {c.from_user.id} selected format: talking_head")
    
    # Сохраняем выбранный формат
    set_video_format(c.from_user.id, "talking_head")
    
    # Переходим к выбору персонажа (обычный флоу)
    await c.message.edit_text(
        "👤 <b>Выбор персонажа</b>\n\n"
        "Сначала выбери пол персонажа:",
        parse_mode="HTML"
    )
    
    # Импортируем здесь, чтобы избежать циклических импортов
    from tg_bot.handlers.character_selection import select_character
    await select_character(c, state)


@dp.callback_query(F.data == "format_character_background")
async def format_character_background_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал формат 'Персонаж с бекграундом'"""
    logger.info(f"User {c.from_user.id} selected format: character_with_background")
    
    # Сохраняем выбранный формат
    set_video_format(c.from_user.id, "character_with_background")
    
    # Просим загрузить фоновое видео
    await c.message.edit_text(
        "🎬 <b>Загрузка фонового видео</b>\n\n"
        "Отправьте видео, которое будет на фоне у персонажа.\n\n"
        "⚠️ <b>Требования:</b>\n"
        "• Формат: MP4, MOV, AVI\n"
        "• Рекомендуемая длительность: до 15 секунд\n\n"
        "Загрузите видео как файл или видео-сообщение.",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    
    # Устанавливаем состояние ожидания загрузки видео
    await state.set_state(UGCCreation.waiting_background_video)
    await c.answer()


@dp.message(UGCCreation.waiting_background_video, F.video | F.document)
async def handle_background_video_upload(m: Message, state: FSMContext):
    """Обработка загруженного фонового видео"""
    logger.info(f"User {m.from_user.id} uploaded background video")
    
    # Отправляем сообщение о начале обработки
    processing_msg = await m.answer("⏳ Проверяю видео...")
    
    try:
        # Получаем file_id и информацию о файле
        if m.video:
            file_id = m.video.file_id
            file_name = f"video_{int(time.time())}.mp4"
        elif m.document:
            file_id = m.document.file_id
            file_name = m.document.file_name or f"video_{int(time.time())}.mp4"
        else:
            await processing_msg.edit_text(
                "❌ Ошибка: неподдерживаемый формат файла.\n"
                "Пожалуйста, отправьте видео файл.",
                reply_markup=back_to_main_menu()
            )
            return
        
        # Скачиваем файл
        from tg_bot.main import bot
        file = await bot.get_file(file_id)
        
        # Создаем временную директорию
        temp_dir = "temp_videos"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file_name)
        
        # Скачиваем файл
        await bot.download_file(file.file_path, temp_path)
        logger.info(f"Downloaded video to {temp_path}")
        
        # Загружаем на R2 (проверку длительности убрали, так как она не работает корректно)
        await processing_msg.edit_text("⏳ Сохраняю видео...")
        
        r2_key = f"users/{m.from_user.id}/backgrounds/background_{int(time.time())}.mp4"
        upload_success = upload_file(temp_path, r2_key)
        
        if not upload_success:
            await processing_msg.edit_text(
                "❌ Ошибка при сохранении видео. Попробуйте еще раз.",
                reply_markup=back_to_main_menu()
            )
            os.remove(temp_path)
            logger.error(f"Failed to upload video to R2 for user {m.from_user.id}")
            return
        
        # Сохраняем путь к фоновому видео в состоянии пользователя
        set_background_video_path(m.from_user.id, r2_key)
        
        # Удаляем временный файл
        os.remove(temp_path)
        logger.info(f"Background video saved to R2: {r2_key}")
        
        # Успешно загружено, переходим к выбору персонажа
        await processing_msg.edit_text(
            f"✅ <b>Видео успешно загружено!</b>\n\n"
            f"Теперь давайте выберем персонажа для вашей рекламы.",
            parse_mode="HTML"
        )
        
        # Переходим к выбору персонажа
        from tg_bot.keyboards import gender_selection_menu
        await m.answer(
            "👤 <b>Выбор персонажа</b>\n\n"
            "Сначала выбери пол персонажа:",
            parse_mode="HTML",
            reply_markup=gender_selection_menu()
        )
        await state.set_state(UGCCreation.waiting_gender_selection)
        
    except Exception as e:
        logger.error(f"Error processing background video: {e}")
        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке видео. Попробуйте еще раз.",
            reply_markup=back_to_main_menu()
        )


@dp.callback_query(F.data == "back_to_format_selection")
async def back_to_format_selection(c: CallbackQuery, state: FSMContext):
    """Возврат к выбору формата"""
    logger.info(f"User {c.from_user.id} returned to format selection")
    await show_format_selection(c, state)


