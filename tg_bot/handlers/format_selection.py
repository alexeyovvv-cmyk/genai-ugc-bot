"""Format selection handlers for the Telegram bot.

This module contains handlers for:
- Video format selection (talking head / character with background)
- Background video upload and validation
- Sending format examples from R2
"""

import os
import time
from aiogram import F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext

from tg_bot.states import UGCCreation
from tg_bot.utils.credits import ensure_user
from tg_bot.utils.user_state import set_video_format, set_background_video_path
from tg_bot.utils.video import check_video_duration_limit
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
    
    # Отправляем текстовое сообщение с выбором формата
    await c.message.edit_text(
        "🎬 <b>Выбор формата видео</b>\n\n"
        "Выберите формат для вашей UGC рекламы:\n\n"
        "👤 <b>Говорящая голова</b> - классический формат с персонажем\n"
        "🎬 <b>Персонаж с бекграундом</b> - персонаж на фоне вашего видео\n\n"
        "Сейчас отправлю примеры форматов...",
        parse_mode="HTML",
        reply_markup=format_selection_menu()
    )
    
    # Устанавливаем состояние ожидания выбора формата
    await state.set_state(UGCCreation.waiting_format_selection)
    await c.answer()
    
    # Отправляем примеры видео из R2 (асинхронно, не блокируем пользователя)
    try:
        await send_format_examples(c.message)
    except Exception as e:
        logger.error(f"Failed to send format examples: {e}")
        await c.message.answer(
            "⚠️ Не удалось загрузить примеры форматов, но вы можете продолжить выбор.",
            parse_mode="HTML"
        )


async def send_format_examples(message):
    """Отправить примеры форматов видео из R2"""
    temp_dir = "temp_downloads"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Пути для временных файлов
    talking_head_path = os.path.join(temp_dir, "example_talking_head.mp4")
    character_bg_path = os.path.join(temp_dir, "example_character_bg.mp4")
    
    try:
        # Попробуем получить presigned URLs для прямой отправки
        talking_head_url = get_presigned_url(EXAMPLE_TALKING_HEAD_KEY, expiry_hours=1)
        character_bg_url = get_presigned_url(EXAMPLE_CHARACTER_BACKGROUND_KEY, expiry_hours=1)
        
        if talking_head_url and character_bg_url:
            # Отправляем URL напрямую (быстрее)
            await message.answer_video(
                talking_head_url,
                caption="📹 <b>Пример: Говорящая голова</b>",
                parse_mode="HTML"
            )
            await message.answer_video(
                character_bg_url,
                caption="📹 <b>Пример: Персонаж с бекграундом</b>",
                parse_mode="HTML"
            )
            logger.info("Format examples sent via presigned URLs")
            return
    except Exception as e:
        logger.warning(f"Failed to send examples via URLs: {e}, trying download method")
    
    # Fallback: скачиваем и отправляем локально
    try:
        # Скачиваем примеры из R2
        if download_file(EXAMPLE_TALKING_HEAD_KEY, talking_head_path):
            await message.answer_video(
                FSInputFile(talking_head_path),
                caption="📹 <b>Пример: Говорящая голова</b>",
                parse_mode="HTML"
            )
            os.remove(talking_head_path)
        
        if download_file(EXAMPLE_CHARACTER_BACKGROUND_KEY, character_bg_path):
            await message.answer_video(
                FSInputFile(character_bg_path),
                caption="📹 <b>Пример: Персонаж с бекграундом</b>",
                parse_mode="HTML"
            )
            os.remove(character_bg_path)
        
        logger.info("Format examples sent via download method")
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
        "• Максимальная длительность: 15 секунд\n"
        "• Формат: MP4, MOV, AVI\n\n"
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
        
        # Проверяем длительность видео
        is_valid, duration = check_video_duration_limit(temp_path, max_seconds=15.0)
        
        if not is_valid:
            # Видео слишком длинное
            await processing_msg.edit_text(
                f"❌ <b>Видео слишком длинное!</b>\n\n"
                f"Длительность вашего видео: <b>{duration:.1f} секунд</b>\n"
                f"Максимально допустимая длительность: <b>15 секунд</b>\n\n"
                f"Пожалуйста, загрузите видео покороче.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            # Удаляем временный файл
            os.remove(temp_path)
            logger.warning(f"User {m.from_user.id} video too long: {duration:.1f}s")
            return
        
        # Видео валидное, загружаем на R2
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
            f"Длительность: <b>{duration:.1f} секунд</b>\n\n"
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


