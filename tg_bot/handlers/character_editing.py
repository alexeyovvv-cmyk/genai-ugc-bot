"""Character editing handlers for the Telegram bot.

This module contains handlers for:
- Character editing decisions
- Edit prompts handling
- Edit result decisions
"""

import os
import time
from aiogram import F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext

from tg_bot.states import UGCCreation
from tg_bot.utils.user_state import (
    get_original_character_path, get_edited_character_path,
    set_original_character_path, set_edited_character_path, 
    increment_edit_iteration, clear_edit_session, set_voice_page
)
from tg_bot.services.nano_banana_service import edit_character_image
from tg_bot.keyboards import (
    edit_result_menu, edit_error_menu
)
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "edit_character_yes")
async def edit_character_yes(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет редактировать персонажа"""
    logger.info(f"User {c.from_user.id} выбрал редактирование персонажа")
    
    try:
        await c.message.answer(
            "📝 <b>Опишите, что хотите изменить в персонаже</b>\n\n"
            "Например:\n"
            "• 'измени фон на пляж'\n"
            "• 'добавь очки'\n"
            "• 'поменяй одежду на деловой костюм'\n"
            "• 'добавь шляпу'\n\n"
            "Чем подробнее опишете, тем лучше результат!",
            parse_mode="HTML"
        )
        logger.info(f"User {c.from_user.id} - сообщение с просьбой ввести промпт отправлено")
        
        await state.set_state(UGCCreation.waiting_edit_prompt)
        logger.info(f"User {c.from_user.id} - состояние установлено: waiting_edit_prompt")
        
        await c.answer()
        logger.info(f"User {c.from_user.id} - callback обработан успешно")
        
    except Exception as e:
        logger.error(f"User {c.from_user.id} - ошибка в edit_character_yes: {e}", exc_info=True)
        await c.answer("❌ Произошла ошибка. Попробуйте еще раз.")


@dp.callback_query(F.data == "edit_character_no")
async def edit_character_no(c: CallbackQuery, state: FSMContext):
    """Пользователь не хочет редактировать персонажа"""
    logger.info(f"User {c.from_user.id} пропустил редактирование персонажа, переходим к выбору голоса")
    # Очищаем сессию редактирования
    clear_edit_session(c.from_user.id)
    # Переходим к выбору голоса
    from tg_bot.handlers.voice_selection import show_voice_gallery
    await show_voice_gallery(c, state)


@dp.message(F.text)
async def debug_text_handler(m: Message, state: FSMContext):
    """DEBUG: Обработчик всех текстовых сообщений"""
    current_state = await state.get_state()
    logger.info(f"🔵 DEBUG: Получено текстовое сообщение от {m.from_user.id}: '{m.text}' в состоянии: {current_state}")

@dp.message(F.text, UGCCreation.waiting_edit_prompt)
async def handle_edit_prompt(m: Message, state: FSMContext):
    """Обработка промпта для редактирования персонажа"""
    logger.info(f"🔴 DEBUG: handle_edit_prompt вызван для пользователя {m.from_user.id}")
    prompt = m.text.strip()
    logger.info(f"User {m.from_user.id} отправил промпт для редактирования: {prompt}")
    logger.info(f"User {m.from_user.id} - текущее состояние FSM: {await state.get_state()}")
    
    if not prompt:
        logger.warning(f"User {m.from_user.id} - пустой промпт")
        await m.answer("❌ Пожалуйста, опишите, что хотите изменить.")
        return
    
    # Показываем сообщение о начале обработки
    logger.info(f"User {m.from_user.id} - начинаем обработку промпта")
    processing_msg = await m.answer("⏳ Редактируем персонажа...")
    logger.info(f"User {m.from_user.id} - сообщение о начале обработки отправлено")
    
    try:
        # Получаем текущее изображение (оригинал или уже отредактированное)
        original_path = get_original_character_path(m.from_user.id)
        edited_path = get_edited_character_path(m.from_user.id)
        current_image_path = edited_path or original_path
        
        logger.info(f"User {m.from_user.id} - original_path: {original_path}, edited_path: {edited_path}, current_image_path: {current_image_path}")
        
        if not current_image_path:
            logger.error(f"User {m.from_user.id} - не найдено изображение персонажа")
            await processing_msg.edit_text("❌ Ошибка: не найдено изображение персонажа.")
            return
        
        # Если current_image_path это R2 ключ, скачиваем его для редактирования
        if current_image_path.startswith("users/"):
            from tg_bot.services.r2_service import download_file
            temp_edit_path = f"data/temp_edits/edit_{int(time.time())}.jpg"
            if download_file(current_image_path, temp_edit_path):
                current_image_path = temp_edit_path
                logger.info(f"Скачали из R2 для редактирования: {current_image_path}")
            else:
                await processing_msg.edit_text("❌ Не удалось загрузить изображение для редактирования.")
                return
        
        # Вызываем сервис редактирования
        logger.info(f"User {m.from_user.id} - вызываем edit_character_image с путем: {current_image_path}")
        new_edited_path = await edit_character_image(current_image_path, prompt)
        logger.info(f"User {m.from_user.id} - edit_character_image вернул: {new_edited_path}")
        
        if new_edited_path:
            # Удаляем предыдущую отредактированную версию, если она была
            if edited_path and edited_path != original_path:
                try:
                    if os.path.exists(edited_path):
                        os.remove(edited_path)
                except Exception as e:
                    logger.warning(f"Could not delete old edited image {edited_path}: {e}")
            
            # Сохраняем новую отредактированную версию
            set_edited_character_path(m.from_user.id, new_edited_path)
            increment_edit_iteration(m.from_user.id)
            
            # Очищаем временный файл редактирования (если был скачан из R2)
            if current_image_path.startswith("data/temp_edits/edit_"):
                try:
                    os.remove(current_image_path)
                    logger.info(f"Удален временный файл редактирования: {current_image_path}")
                except Exception as e:
                    logger.warning(f"Ошибка при удалении временного файла: {e}")
            
            # Показываем результат
            await processing_msg.delete()
            await m.answer("✨ <b>Вот результат!</b>", parse_mode="HTML")
            
            # Проверяем, нужно ли скачать из R2 для показа
            if new_edited_path.startswith("users/"):
                # Это R2 ключ - скачиваем для показа
                from tg_bot.services.r2_service import download_file
                temp_show_path = f"data/temp_edits/show_{int(time.time())}.jpg"
                if download_file(new_edited_path, temp_show_path):
                    await m.answer_photo(FSInputFile(temp_show_path))
                    # НЕ удаляем временный файл - он может понадобиться для:
                    # 1. Video generation (если пользователь выберет "использовать эту редакцию")
                    # 2. Следующего редактирования (если выберет "редактировать дальше")
                    # Удалим его только при финальном выборе
                else:
                    await m.answer("❌ Не удалось загрузить изображение для показа")
            else:
                # Локальный путь
                await m.answer_photo(FSInputFile(new_edited_path))
            
            await m.answer(
                "Что хотите сделать дальше?",
                reply_markup=edit_result_menu()
            )
            await state.set_state(UGCCreation.waiting_edit_result_decision)
        else:
            await processing_msg.edit_text(
                "❌ <b>Что-то пошло не так при редактировании</b>\n\n"
                "Попробуйте другой промпт или используйте оригинальное изображение.",
                parse_mode="HTML",
                reply_markup=edit_error_menu()
            )
            await state.set_state(UGCCreation.waiting_edit_result_decision)
            
    except Exception as e:
        logger.error(f"User {m.from_user.id} - Error in character editing: {e}", exc_info=True)
        await processing_msg.edit_text(
            "❌ <b>Произошла ошибка при редактировании</b>\n\n"
            "Попробуйте другой промпт или используйте оригинальное изображение.",
            parse_mode="HTML",
            reply_markup=edit_error_menu()
        )
        await state.set_state(UGCCreation.waiting_edit_result_decision)


@dp.callback_query(F.data == "use_edited_character")
async def use_edited_character(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал использовать отредактированную версию"""
    # Получаем путь к отредактированному изображению
    edited_path = get_edited_character_path(c.from_user.id)
    
    if edited_path and os.path.exists(edited_path):
        # НЕ заменяем оригинальный файл в папке персонажей!
        # Вместо этого просто оставляем отредактированный путь как финальный
        # В video generation мы будем проверять edited_character_path
        logger.info(f"Пользователь выбрал использовать отредактированную версию: {edited_path}")
        logger.info(f"Отредактированное изображение будет использоваться в video generation")
    else:
        logger.warning(f"Отредактированное изображение не найдено")
    
    # НЕ очищаем сессию редактирования - оставляем edited_character_path
    # Очищаем только счетчик итераций и original_character_path
    # Очищаем только ненужные поля, но оставляем edited_character_path
    set_original_character_path(c.from_user.id, None)
    # edited_character_path остается для использования в video generation
    
    # Очищаем временный файл показа (если был скачан из R2)
    try:
        import glob
        temp_files = glob.glob("data/temp_edits/show_*.jpg")
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"Удален временный файл показа: {temp_file}")
    except Exception as e:
        logger.warning(f"Ошибка при очистке временных файлов: {e}")
    
    # Переходим к выбору голоса
    from tg_bot.handlers.voice_selection import show_voice_gallery
    await show_voice_gallery(c, state)


@dp.callback_query(F.data == "use_original_character")
async def use_original_character(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал использовать оригинальную версию"""
    # Удаляем отредактированную версию, если она есть
    edited_path = get_edited_character_path(c.from_user.id)
    if edited_path:
        try:
            # Check if it's R2 key or local path
            if edited_path.startswith("users/"):
                # It's R2 key - delete from R2
                from tg_bot.services.r2_service import delete_file
                if delete_file(edited_path):
                    logger.info(f"Удалено из R2: {edited_path}")
                else:
                    logger.warning(f"Не удалось удалить из R2: {edited_path}")
            else:
                # Legacy local path
                if os.path.exists(edited_path):
                    os.remove(edited_path)
                    logger.info(f"Локальный файл удален: {edited_path}")
        except Exception as e:
            logger.warning(f"Could not delete edited image {edited_path}: {e}")
    
    # Очищаем сессию редактирования
    clear_edit_session(c.from_user.id)
    
    # Очищаем временный файл показа (если был скачан из R2)
    try:
        import glob
        temp_files = glob.glob("data/temp_edits/show_*.jpg")
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"Удален временный файл показа: {temp_file}")
    except Exception as e:
        logger.warning(f"Ошибка при очистке временных файлов: {e}")
    
    # Переходим к выбору голоса
    from tg_bot.handlers.voice_selection import show_voice_gallery
    await show_voice_gallery(c, state)


@dp.callback_query(F.data == "continue_editing")
async def continue_editing(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет продолжить редактирование"""
    await c.message.answer(
        "📝 <b>Опишите следующие изменения</b>\n\n"
        "Что еще хотите изменить в персонаже?",
        parse_mode="HTML"
    )
    await state.set_state(UGCCreation.waiting_edit_prompt)
    await c.answer()


@dp.callback_query(F.data == "retry_edit_prompt")
async def retry_edit_prompt(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет попробовать другой промпт"""
    await c.message.answer(
        "📝 <b>Попробуйте другой промпт</b>\n\n"
        "Опишите изменения по-другому или более конкретно.",
        parse_mode="HTML"
    )
    await state.set_state(UGCCreation.waiting_edit_prompt)
    await c.answer()
