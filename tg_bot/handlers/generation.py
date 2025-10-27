"""Generation handlers for the Telegram bot.

This module contains handlers for:
- Audio generation and confirmation
- Video generation
- Text input handling
- Audio redo functionality
"""

import os
import sys
import time
from aiogram import F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from tg_bot.states import UGCCreation
from tg_bot.utils.credits import get_credits, spend_credits, add_credits
from tg_bot.utils.constants import COST_UGC_VIDEO
from tg_bot.utils.user_state import (
    get_selected_character, get_character_text, set_character_text,
    get_last_audio, set_last_audio,
    get_character_gender, get_character_age,
    get_original_character_path, get_edited_character_path,
    clear_edit_session
)
from tg_bot.utils.voice_mapping import get_voice_for_character, get_default_language, get_default_emotion
from tg_bot.utils.files import get_character_image
from tg_bot.utils.audio import check_audio_duration_limit
from tg_bot.services.minimax_service import tts_to_file
from tg_bot.services.falai_service import generate_talking_head_video
from tg_bot.services.r2_service import download_file, delete_file
from tg_bot.keyboards import (
    back_to_main_menu, main_menu
)
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.message(StateFilter(UGCCreation.waiting_character_text), F.text)
async def character_text_received(m: Message, state: FSMContext):
    """Получен текст от пользователя - сразу генерируем видео"""
    # Сохраняем текст
    set_character_text(m.from_user.id, m.text)
    logger.info(f"User {m.from_user.id} ввел текст персонажа: {m.text[:50]}...")
    
    # Получаем параметры персонажа для автовыбора голоса
    gender = get_character_gender(m.from_user.id)
    age = get_character_age(m.from_user.id)
    
    if not gender:
        await m.answer(
            "❌ Не выбраны параметры персонажа. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    # Автоматически определяем голос по полу персонажа
    voice_id = get_voice_for_character(gender, age)
    language = get_default_language()
    emotion = get_default_emotion()
    
    logger.info(f"[UGC] Автовыбор голоса: gender={gender}, voice_id={voice_id}")
    
    try:
        # Проверяем кредиты
        credits = get_credits(m.from_user.id)
        if credits < COST_UGC_VIDEO:
            await m.answer(
                f"❌ Недостаточно кредитов (нужно {COST_UGC_VIDEO} кредит).\n\n"
                "Свяжись с администратором для пополнения.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
        
        # Списываем кредит
        ok = spend_credits(m.from_user.id, COST_UGC_VIDEO, "ugc_video_creation")
        if not ok:
            await m.answer(
                "❌ Ошибка при списании кредита.\n\n"
                "Свяжись с администратором.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
    
        # Генерируем аудио (не показываем пользователю)
        await m.answer("🎤 Генерирую озвучку...")
        logger.info(f"[UGC] Генерация MiniMax TTS для пользователя {m.from_user.id}, voice_id={voice_id}")
        
        audio_path = await tts_to_file(m.text, voice_id, language, emotion, user_id=m.from_user.id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        logger.info(f"[UGC] Аудио сгенерировано: {audio_path}")
        
        # Сохраняем путь к аудио
        set_last_audio(m.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        logger.info(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            # Возвращаем кредит при ошибке
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_audio_too_long")
            await m.answer(
                f"❌ <b>Аудио слишком длинное!</b>\n\n"
                f"Длительность твоей озвучки: <b>{duration:.1f} секунд</b>\n"
                f"Максимум: <b>15 секунд</b>\n\n"
                f"Пожалуйста, сократи текст и попробуй снова.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            # Очистка аудио
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except:
                pass
            await state.clear()
            return
        
        # Сразу переходим к генерации видео (логика из audio_confirmed)
        await m.answer("⏳ Начинаю создание UGC рекламы...\n\nЭто займет несколько минут.")
        logger.info(f"[UGC] Стартовое сообщение отправлено")
        
        # Получаем сохраненные данные
        character_idx = get_selected_character(m.from_user.id)
        
        # Получаем изображение персонажа (сначала проверяем отредактированную версию)
        if not gender or not age or character_idx is None:
            raise Exception("Не выбраны параметры персонажа (пол, возраст или индекс). Начните сначала.")
        
        # Проверяем, есть ли отредактированная версия
        edited_character_path = get_edited_character_path(m.from_user.id)
        temp_edited_path = None
        
        if edited_character_path:
            # Check if it's R2 key or local path
            if edited_character_path.startswith("users/"):
                # It's R2 key - download to temp for video generation
                temp_edited_path = f"data/temp_edits/temp_{int(time.time())}.jpg"
                
                if download_file(edited_character_path, temp_edited_path):
                    selected_frame = temp_edited_path
                    logger.info(f"[UGC] Используем отредактированную версию из R2: {edited_character_path}")
                else:
                    logger.info(f"[UGC] Не удалось скачать из R2, используем оригинал")
                    character_data = get_character_image(gender, character_idx)
                    selected_frame = character_data[0] if character_data else None
            else:
                # Legacy local path support
                if os.path.exists(edited_character_path):
                    selected_frame = edited_character_path
                    logger.info(f"[UGC] Используем локальную отредактированную версию: {edited_character_path}")
                else:
                    logger.info(f"[UGC] Файл не найден, используем оригинал")
                    character_data = get_character_image(gender, character_idx)
                    selected_frame = character_data[0] if character_data else None
        else:
            # No edited version
            character_data = get_character_image(gender, character_idx)
            if character_data:
                selected_frame, detected_age = character_data
                logger.info(f"[UGC] Используем оригинальную систему персонажей: {gender}/{detected_age}, индекс {character_idx}")
            else:
                selected_frame = None
        
        if not selected_frame:
            logger.info(f"[UGC] ❌ Кадр не найден!")
            if gender:
                raise Exception(f"Не удалось найти персонажа с параметрами: пол={gender}, индекс={character_idx}")
            else:
                raise Exception("Не удалось найти выбранный кадр")
        
        if not audio_path or not os.path.exists(audio_path):
            logger.info(f"[UGC] ❌ Аудио не найдено!")
            raise Exception("Не удалось найти аудио файл")
        
        logger.info(f"[UGC] Выбран кадр: {selected_frame}")
        
        # Генерируем видео с помощью fal.ai OmniHuman
        logger.info(f"[UGC] Начинаем генерацию talking head видео через fal.ai...")
        logger.info(f"[UGC] Стартовый кадр: {selected_frame}")
        logger.info(f"[UGC] Аудио файл: {audio_path}")
        
        try:
            logger.info(f"[UGC] Calling generate_talking_head_video with user_id: {m.from_user.id}")
            video_result = await generate_talking_head_video(
                audio_path=audio_path,
                image_path=selected_frame,
                user_id=m.from_user.id
            )
            
            if not video_result:
                logger.error(f"[UGC] ❌ generate_talking_head_video вернул None")
                raise Exception("Не удалось сгенерировать видео")
            
            video_path = video_result['local_path']
            video_url = video_result.get('video_url')
            r2_video_key = video_result.get('r2_video_key')
            
            logger.info(f"[UGC] Видео сгенерировано: {video_path}")
            logger.info(f"[UGC] Video URL: {video_url}")
            logger.info(f"[UGC] R2 Video Key: {r2_video_key}")
            if r2_video_key:
                logger.info(f"[UGC] Видео сохранено в R2: {r2_video_key}")
            else:
                logger.info(f"[UGC] ⚠️ R2 Video Key is None - video not saved to R2")
        except Exception as video_error:
            logger.error(f"[UGC] ❌ Ошибка при генерации видео: {video_error}")
            import traceback
            traceback.print_exc()
            # Авто-рефанд кредита при неуспехе генерации
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise video_error  # Перебрасываем оригинальную ошибку без обертки
        
        if video_path:
            await m.answer("✅ Отправляю готовое видео...")
            logger.info(f"[UGC] Отправляем видео пользователю...")
            
            # Отправляем видео (используем presigned URL если есть, иначе локальный файл)
            if video_url:
                await m.answer_video(
                    video_url, 
                    caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)"
                )
                logger.info(f"[UGC] ✅ Видео отправлено через R2 URL")
            else:
                await m.answer_video(
                    FSInputFile(video_path), 
                    caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)"
                )
                logger.info(f"[UGC] ✅ Видео отправлено через локальный файл")
            
            # Сохраняем генерацию в историю
            try:
                from tg_bot.utils.user_storage import save_user_generation
                logger.info(f"[UGC] Сохраняем генерацию в историю...")
                logger.info(f"[UGC] User ID: {m.from_user.id}")
                logger.info(f"[UGC] R2 Video Key: {r2_video_key}")
                logger.info(f"[UGC] Character: {get_character_gender(m.from_user.id)}/{get_character_age(m.from_user.id)}")
                logger.info(f"[UGC] Text: {get_character_text(m.from_user.id)}")
                
                generation_id = save_user_generation(
                    user_id=m.from_user.id,
                    generation_type='video',
                    r2_video_key=r2_video_key,
                    r2_audio_key=None,  # Аудио включено в MP4, не сохраняем отдельно
                    character_gender=get_character_gender(m.from_user.id),
                    character_age=get_character_age(m.from_user.id),
                    text_prompt=get_character_text(m.from_user.id),
                    credits_spent=COST_UGC_VIDEO
                )
                logger.info(f"[UGC] ✅ Генерация сохранена в историю с ID: {generation_id}")
            except Exception as save_error:
                logger.info(f"[UGC] ⚠️ Не удалось сохранить генерацию в историю: {save_error}")
                import traceback
                traceback.print_exc()
            
            # Удаляем видео файл после отправки
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                    logger.info(f"[UGC] ✅ Видео файл удален: {video_path}")
            except Exception as cleanup_error:
                logger.info(f"[UGC] ⚠️ Не удалось удалить видео файл: {cleanup_error}")
            
            # Очищаем временные отредактированные изображения персонажа
            try:
                edited_path = get_edited_character_path(m.from_user.id)
                if edited_path:
                    # Check if it's R2 key or local path
                    if edited_path.startswith("users/"):
                        # It's R2 key - delete from R2
                        if delete_file(edited_path):
                            logger.info(f"[UGC] ✅ Отредактированное изображение удалено из R2: {edited_path}")
                        else:
                            logger.info(f"[UGC] ⚠️ Не удалось удалить из R2: {edited_path}")
                    else:
                        # Legacy local path
                        if os.path.exists(edited_path):
                            os.remove(edited_path)
                            logger.info(f"[UGC] ✅ Локальное отредактированное изображение удалено: {edited_path}")
                    
                    # Also delete temp file if downloaded from R2
                    if temp_edited_path and os.path.exists(temp_edited_path):
                        os.remove(temp_edited_path)
                        logger.info(f"[UGC] ✅ Временный файл удален: {temp_edited_path}")
                
                # Очищаем сессию редактирования
                clear_edit_session(m.from_user.id)
                logger.info(f"[UGC] ✅ Сессия редактирования очищена")
            except Exception as cleanup_error:
                logger.info(f"[UGC] ⚠️ Не удалось очистить временные файлы редактирования: {cleanup_error}")
        else:
            # Авто-рефанд если видео не получено
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise Exception("Видео не было сгенерировано")
        
        # Очищаем состояние
        await state.clear()
        logger.info(f"[UGC] Состояние очищено")
        
        # Предлагаем создать еще одно видео
        await m.answer(
            "🎬 Хочешь создать еще одну UGC рекламу?",
            reply_markup=main_menu()
        )
        
    except Exception as e:
        logger.info(f"[UGC] ❌ Критическая ошибка при создании UGC рекламы: {e}")
        import traceback
        traceback.print_exc()
        
        # Очищаем временные файлы редактирования при ошибке
        try:
            edited_path = get_edited_character_path(m.from_user.id)
            if edited_path and os.path.exists(edited_path):
                os.remove(edited_path)
                logger.info(f"[UGC] ✅ Временное отредактированное изображение удалено при ошибке: {edited_path}")
            clear_edit_session(m.from_user.id)
            logger.info(f"[UGC] ✅ Сессия редактирования очищена при ошибке")
        except Exception as cleanup_error:
            logger.info(f"[UGC] ⚠️ Не удалось очистить временные файлы при ошибке: {cleanup_error}")
        
        # Скрываем технические ошибки от пользователей
        error_message = "❌ Произошла ошибка при создании видео"
        if "Exhausted balance" in str(e) or "User is locked" in str(e) or "TTS service temporarily unavailable" in str(e):
            error_message += "\n\n🔧 Сервис временно недоступен. Попробуй позже."
        elif "заблокировано системой безопасности" in str(e) or "content_policy_violation" in str(e):
            error_message += "\n\n🚫 Изображение персонажа заблокировано системой безопасности.\n\nПопробуй выбрать другого персонажа."
            
            # Возвращаем кредит
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_content_policy_violation")
            
            # Очищаем состояние и возвращаем к выбору персонажа
            await state.clear()
            
            # Отправляем сообщение с кнопкой выбора персонажа
            from tg_bot.keyboards import gender_selection_menu
            await m.answer(
                "🚫 <b>Изображение персонажа заблокировано системой безопасности</b>\n\n"
                "Попробуй выбрать другого персонажа:",
                parse_mode="HTML",
                reply_markup=gender_selection_menu()
            )
            await state.set_state(UGCCreation.waiting_gender_selection)
            return
        else:
            if "API" in str(e) or "fal.ai" in str(e) or "TTS service error" in str(e):
                error_message += "\n\n🔧 Проблема с сервисом генерации. Попробуй позже."
            else:
                error_message += "\n\nПопробуй еще раз или свяжись с администратором."
            
            await m.answer(
                error_message,
                reply_markup=main_menu()
            )
            await state.clear()


