"""
Handlers for video editing functionality.

This module handles:
- Video editing (subtitles, compositing)
- Finishing generation flow without editing
- Re-editing support (multiple iterations)
"""
import logging
from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from tg_bot.states import UGCCreation
from tg_bot.keyboards import main_menu, video_editing_menu
from tg_bot.utils.user_state import (
    get_original_video,
    get_last_generated_video,
    set_last_generated_video,
    clear_all_video_data,
    get_video_format,
    get_background_video_path,
    get_character_text
)
from tg_bot.services.video_editing_service import (
    add_subtitles_to_video,
    composite_head_with_background,
    VideoEditingError
)
from tg_bot.dispatcher import dp
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)


@dp.callback_query(F.data == "start_video_editing", StateFilter(UGCCreation.waiting_editing_decision))
async def start_video_editing(c: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Монтаж'"""
    await c.answer()
    
    try:
        # Получаем данные исходного видео (используем original_video для повторных монтажей)
        video_data = get_original_video(c.from_user.id)
        if not video_data or not video_data.get('r2_key'):
            await c.message.answer("❌ Не найдено видео для монтажа")
            await state.clear()
            await c.message.answer("Создайте новое видео:", reply_markup=main_menu())
            return
        
        video_r2_key = video_data['r2_key']
        video_format = get_video_format(c.from_user.id)
        text = get_character_text(c.from_user.id) or ""
        
        logger.info(f"Starting video editing for user {c.from_user.id}, format={video_format}")
        
        # Отправляем статусное сообщение
        status_msg = await c.message.answer("⏳ Начинаю монтаж видео...")
        
        try:
            if video_format == "talking_head":
                # Сценарий 1: Добавить субтитры к говорящей голове
                logger.info(f"Adding subtitles to talking head video for user {c.from_user.id}")
                
                await status_msg.edit_text("⏳ Накладываю субтитры...")
                
                result = await add_subtitles_to_video(
                    video_r2_key=video_r2_key,
                    text=text,
                    user_id=c.from_user.id
                )
                
                await status_msg.edit_text("⏳ Рендерю финальное видео (это может занять 1-2 минуты)...")
                
            elif video_format == "character_with_background":
                # Сценарий 2: Композитинг головы с фоном
                background_r2_key = get_background_video_path(c.from_user.id)
                if not background_r2_key:
                    await status_msg.delete()
                    await c.message.answer(
                        "❌ Не найдено фоновое видео.\n\n"
                        "Попробуйте еще раз или завершите:",
                        reply_markup=video_editing_menu()
                    )
                    return
                
                logger.info(f"Compositing head with background for user {c.from_user.id}")
                
                await status_msg.edit_text("⏳ Монтирую видео с фоном...")
                
                result = await composite_head_with_background(
                    head_r2_key=video_r2_key,
                    background_r2_key=background_r2_key,
                    text=text,
                    user_id=c.from_user.id
                )
                
                await status_msg.edit_text("⏳ Рендерю финальное видео (это может занять 1-2 минуты)...")
                
            else:
                # Неизвестный формат - применяем базовый монтаж
                logger.warning(f"Unknown video format '{video_format}' for user {c.from_user.id}, using talking_head")
                
                await status_msg.edit_text("⏳ Накладываю субтитры...")
                
                result = await add_subtitles_to_video(
                    video_r2_key=video_r2_key,
                    text=text,
                    user_id=c.from_user.id
                )
            
            # Сохраняем результат монтажа
            set_last_generated_video(
                c.from_user.id,
                result.get('r2_key'),
                result.get('url')
            )
            logger.info(f"Saved edited video for user {c.from_user.id}")
            
            # Удаляем статусное сообщение
            await status_msg.delete()
            
            # Отправляем готовое видео
            await c.message.answer("✅ Монтаж завершен! Отправляю видео...")
            
            if result.get('url'):
                await c.message.answer_video(
                    result['url'],
                    caption="🎬 Твое видео с монтажом готово!"
                )
            else:
                await c.message.answer("✅ Видео смонтировано и сохранено в хранилище")
            
            logger.info(f"Video editing completed for user {c.from_user.id}")
            
            # ✨ НЕ ОЧИЩАЕМ СОСТОЯНИЕ - возвращаем к выбору для повторного монтажа
            await c.message.answer(
                "🎬 Хочешь смонтировать еще раз или завершить?\n\n"
                "💡 Ты можешь попробовать другой вариант монтажа!",
                reply_markup=video_editing_menu()
            )
            
        except VideoEditingError as e:
            logger.error(f"Video editing error for user {c.from_user.id}: {e}")
            await status_msg.delete()
            
            # ✨ НЕ ОЧИЩАЕМ СОСТОЯНИЕ - даем повторить попытку
            await c.message.answer(
                "❌ Произошла ошибка при монтаже видео.\n\n"
                "Попробуйте еще раз или завершите:",
                reply_markup=video_editing_menu()
            )
            # Остаемся в состоянии waiting_editing_decision
            
        except Exception as e:
            logger.error(f"Unexpected error in video editing for user {c.from_user.id}: {e}", exc_info=True)
            await status_msg.delete()
            
            # ✨ НЕ ОЧИЩАЕМ СОСТОЯНИЕ - даем повторить попытку
            await c.message.answer(
                "❌ Произошла неожиданная ошибка.\n\n"
                "Попробуйте еще раз или завершите:",
                reply_markup=video_editing_menu()
            )
            # Остаемся в состоянии waiting_editing_decision
        
    except Exception as e:
        logger.error(f"Error in start_video_editing for user {c.from_user.id}: {e}", exc_info=True)
        await state.clear()
        await c.message.answer(
            "❌ Произошла критическая ошибка. Попробуйте создать новое видео.",
            reply_markup=main_menu()
        )


@dp.callback_query(F.data == "finish_generation", StateFilter(UGCCreation.waiting_editing_decision))
async def finish_generation(c: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Завершить' (без монтажа или после монтажа)"""
    await c.answer()
    
    logger.info(f"User {c.from_user.id} finished generation")
    
    # Проверяем, был ли монтаж
    edited_video = get_last_generated_video(c.from_user.id)
    
    if edited_video and edited_video.get('r2_key'):
        # Был монтаж - показываем финальный результат
        await c.message.edit_text(
            "✅ Отлично! Видео с монтажом готово.\n\n"
            "🎬 Хочешь создать еще одну UGC рекламу?"
        )
    else:
        # Монтажа не было - просто завершаем
        await c.message.edit_text(
            "✅ Отлично! Видео готово.\n\n"
            "🎬 Хочешь создать еще одну UGC рекламу?"
        )
    
    # Очищаем все данные о видео
    clear_all_video_data(c.from_user.id)
    
    # Очищаем состояние
    await state.clear()
    
    # Возвращаемся в главное меню
    await c.message.answer(
        "Выбери действие:",
        reply_markup=main_menu()
    )
