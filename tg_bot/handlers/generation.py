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
    clear_edit_session,
    set_original_video
)
from tg_bot.utils.voice_mapping import get_voice_for_character, get_default_language, get_default_emotion
from tg_bot.utils.files import get_character_image
from tg_bot.utils.audio import check_audio_duration_limit, concatenate_audio_files
from tg_bot.utils.emotion_mapping import normalize_emotion
from tg_bot.utils.constants import DEFAULT_TTS_EMOTION
from tg_bot.services.openai_enhancement_service import enhance_prompt, parse_emotion_segments
from tg_bot.services.minimax_service import tts_to_file
from tg_bot.services.falai_service import generate_talking_head_video
from tg_bot.services.r2_service import download_file, delete_file
from tg_bot.keyboards import (
    back_to_main_menu, main_menu, video_editing_menu, segment_confirmation_menu,
    audio_confirmation_menu
)
from tg_bot.config import BASE_DIR
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.message(StateFilter(UGCCreation.waiting_character_text), F.text)
async def character_text_received(m: Message, state: FSMContext):
    """Получен текст от пользователя - применяем prompt enhancement и показываем разбивку"""
    # Сохраняем исходный текст
    set_character_text(m.from_user.id, m.text)
    logger.info(f"[GENERATION] User {m.from_user.id} entered text: {m.text[:100]}...")
    
    # Получаем параметры персонажа
    gender = get_character_gender(m.from_user.id)
    age = get_character_age(m.from_user.id)
    
    if not gender:
        await m.answer(
            "❌ Не выбраны параметры персонажа. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    try:
        # Показываем что обрабатываем текст
        await m.answer("🤖 Обрабатываю текст и анализирую эмоции...")
        
        # Вызываем prompt enhancement
        logger.info(f"[GENERATION] Starting prompt enhancement...")
        enhanced_text = await enhance_prompt(m.text)
        
        # Парсим сегменты с эмоциями
        segments = parse_emotion_segments(enhanced_text)
        
        if not segments:
            # Если парсинг не удался, используем исходный текст без разбивки
            logger.warning(f"[ENHANCEMENT] No segments parsed, using original text")
            segments = [{"emotion": DEFAULT_TTS_EMOTION, "text": m.text}]
        
        # Нормализуем эмоции
        for segment in segments:
            segment['emotion'] = normalize_emotion(segment['emotion'])
        
        logger.info(f"[GENERATION] Showing {len(segments)} segments to user for confirmation")
        
        # Сохраняем сегменты в state
        await state.update_data(emotion_segments=segments)
        
        # Формируем сообщение с разбивкой
        segments_text = "Разбивка по эмоциям:\n\n"
        for i, segment in enumerate(segments, 1):
            segments_text += f"{i}. [{segment['emotion']}] {segment['text']}\n\n"
        
        segments_text += "Подтвердить эту разбивку?"
        
        # Показываем пользователю разбивку
        await m.answer(
            segments_text,
            reply_markup=segment_confirmation_menu()
        )
        
        # Устанавливаем состояние ожидания подтверждения
        await state.set_state(UGCCreation.waiting_segment_confirmation)
        
    except Exception as e:
        logger.error(f"[ENHANCEMENT] OpenAI API error: {e}")
        await m.answer(
            "❌ Ошибка обработки текста. Попробуй еще раз.",
            reply_markup=back_to_main_menu()
        )
        return


@dp.callback_query(F.data == "cancel_segments")
async def cancel_segments(c: CallbackQuery, state: FSMContext):
    """Отменить разбивку и вернуться к вводу текста."""
    logger.info(f"[GENERATION] User {c.from_user.id} cancelled emotion segments, returning to text input")
    await c.message.edit_text("Введите текст заново:")
    await state.set_state(UGCCreation.waiting_character_text)
    await c.answer()


@dp.callback_query(F.data == "confirm_segments")
async def confirm_segments(c: CallbackQuery, state: FSMContext):
    """Подтвердить эмоциональную разбивку и начать генерацию аудио."""
    logger.info(f"[GENERATION] User {c.from_user.id} confirmed emotion segments")
    
    # Получаем сегменты из FSM state
    data = await state.get_data()
    segments = data.get('emotion_segments', [])
    logger.info(f"[GENERATION] Starting TTS generation for {len(segments)} segments")
    
    # Получаем параметры персонажа для автовыбора голоса
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    
    # Автоматически определяем голос по полу персонажа
    voice_id = get_voice_for_character(gender, age)
    language = get_default_language()
    
    logger.info(f"[UGC] Автовыбор голоса: gender={gender}, voice_id={voice_id}")
    
    try:
        # Проверяем кредиты
        credits = get_credits(c.from_user.id)
        if credits < COST_UGC_VIDEO:
            await m.answer(
                f"❌ Недостаточно кредитов (нужно {COST_UGC_VIDEO} кредит).\n\n"
                "Свяжись с администратором для пополнения.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
        
        # Списываем кредит
        ok = spend_credits(c.from_user.id, COST_UGC_VIDEO, "ugc_video_creation")
        if not ok:
            await c.message.answer(
                "❌ Ошибка при списании кредита.\n\n"
                "Свяжись с администратором.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
    
        # Генерируем N отдельных аудио для каждого сегмента с эмоциями
        await c.message.answer(f"🎤 Генерирую озвучку ({len(segments)} сегментов)...")
        logger.info(f"[UGC] Генерация MiniMax TTS для пользователя {c.from_user.id}, voice_id={voice_id}")
        
        audio_paths = []
        for i, segment in enumerate(segments):
            logger.info(f"[GENERATION] Segment {i+1}/{len(segments)}: emotion={segment['emotion']}, text={segment['text'][:50]}...")
            
            # ВАЖНО: Отдельный запрос для каждого сегмента с его эмоцией
            try:
                audio_path = await tts_to_file(
                    text=segment['text'],
                    voice_id=voice_id,
                    language=language,
                    emotion=segment['emotion'],  # Передать эмоцию из тега
                    user_id=c.from_user.id
                )
                
                if not audio_path:
                    raise Exception(f"Не удалось сгенерировать аудио для сегмента {i+1}")
                
                logger.info(f"[GENERATION] Segment {i+1} TTS completed: {audio_path}")
                audio_paths.append(audio_path)
                
            except Exception as e:
                logger.error(f"[GENERATION] TTS failed for segment {i+1}: {e}")
                # Возвращаем кредит при ошибке
                add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_tts_fail")
                await c.message.answer(
                    f"❌ Ошибка генерации аудио. Попробуйте позже.",
                    reply_markup=main_menu()
                )
                await state.clear()
                return
        
        logger.info(f"[GENERATION] All {len(audio_paths)} TTS segments generated successfully")
        
        # Склеить все аудио в том же порядке с паузами
        logger.info(f"[GENERATION] Starting audio concatenation...")
        timestamp = int(time.time())
        audio_dir = BASE_DIR / "data" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        final_audio_path = str(audio_dir / f"final_audio_{c.from_user.id}_{timestamp}.mp3")
        
        try:
            final_audio_path = await concatenate_audio_files(
                audio_paths=audio_paths,
                output_path=final_audio_path,
                pause_duration_ms=130
            )
            logger.info(f"[GENERATION] Audio concatenation completed: {final_audio_path}")
        except Exception as e:
            logger.error(f"[AUDIO_CONCAT] Concatenation failed: {e}")
            # Fallback: использовать первый аудио файл
            if audio_paths:
                final_audio_path = audio_paths[0]
                logger.warning(f"[AUDIO_CONCAT] Using first segment as fallback: {final_audio_path}")
            else:
                raise Exception("Не удалось сгенерировать аудио")
        
        audio_path = final_audio_path
        
        # Сохраняем путь к аудио
        set_last_audio(c.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=30.0)
        
        logger.info(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            # Возвращаем кредит при ошибке
            add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_audio_too_long")
            await c.message.answer(
                f"❌ <b>Аудио слишком длинное!</b>\n\n"
                f"Длительность твоей озвучки: <b>{duration:.1f} секунд</b>\n"
                f"Максимум: <b>30 секунд</b>\n\n"
                f"Пожалуйста, сократи текст и попробуй снова.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            # Очистка аудио и временных файлов
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                # Очищаем временные сегменты
                for temp_path in audio_paths:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            except:
                pass
            await state.clear()
            return
        
        # Отправляем склеенное аудио пользователю для прослушивания
        await c.message.answer("🎧 Вот как будет звучать озвучка:")
        
        try:
            # Отправляем аудио файл
            await c.message.answer_audio(
                FSInputFile(audio_path),
                caption="Послушай результат. Если всё устраивает - подтверди генерацию видео."
            )
            logger.info(f"[GENERATION] Audio sent to user for confirmation")
            
            # Устанавливаем состояние ожидания подтверждения аудио
            await state.set_state(UGCCreation.waiting_audio_confirmation)
            
            # Показываем клавиатуру с подтверждением
            await c.message.answer(
                "Подтвердить озвучку?",
                reply_markup=audio_confirmation_menu()
            )
            await c.answer()
            
        except Exception as audio_send_error:
            logger.error(f"[GENERATION] Failed to send audio: {audio_send_error}")
            await c.message.answer(
                "❌ Не удалось отправить аудио. Попробуй еще раз.",
                reply_markup=back_to_main_menu()
            )
            await state.clear()
            return
    
    except Exception as e:
        logger.error(f"[GENERATION] Error in confirm_segments: {e}")
        import traceback
        traceback.print_exc()
        
        # Возвращаем кредит при ошибке
        add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_segment_error")
        
        await c.message.answer(
            "❌ Произошла ошибка при генерации аудио. Попробуй еще раз.",
            reply_markup=main_menu()
        )
        await state.clear()
        await c.answer()


@dp.callback_query(F.data == "audio_redo")
async def audio_redo(c: CallbackQuery, state: FSMContext):
    """Переделать аудио - возвращаемся к вводу текста."""
    logger.info(f"[GENERATION] User {c.from_user.id} requested audio redo, returning to text input")
    
    await c.message.answer("Напиши текст заново:")
    await state.set_state(UGCCreation.waiting_character_text)
    await c.answer()


@dp.callback_query(F.data == "audio_confirmed")
async def audio_confirmed(c: CallbackQuery, state: FSMContext):
    """Подтверждение аудио - начинаем генерацию видео."""
    logger.info(f"[GENERATION] User {c.from_user.id} confirmed audio, starting video generation")
    
    # Получаем сохраненный аудио путь
    audio_path = get_last_audio(c.from_user.id)
    
    if not audio_path or not os.path.exists(audio_path):
        await c.message.answer(
            "❌ Аудио файл не найден. Попробуй еще раз.",
            reply_markup=main_menu()
        )
        await state.clear()
        await c.answer()
        return
    
    # Получаем параметры персонажа
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    character_idx = get_selected_character(c.from_user.id)
    
    try:
        # Начинаем генерацию видео
        await c.message.answer("⏳ Начинаю создание UGC рекламы...\n\nЭто займет несколько минут.")
        logger.info(f"[UGC] Стартовое сообщение отправлено")
        
        # Получаем изображение персонажа (сначала проверяем отредактированную версию)
        if not gender or not age or character_idx is None:
            raise Exception("Не выбраны параметры персонажа (пол, возраст или индекс). Начните сначала.")
        
        # Проверяем, есть ли отредактированная версия
        edited_character_path = get_edited_character_path(c.from_user.id)
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
            logger.info(f"[UGC] Calling generate_talking_head_video with user_id: {c.from_user.id}")
            video_result = await generate_talking_head_video(
                audio_path=audio_path,
                image_path=selected_frame,
                user_id=c.from_user.id
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
            add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise video_error  # Перебрасываем оригинальную ошибку без обертки
        
        if video_path:
            await c.message.answer("✅ Отправляю готовое видео...")
            logger.info(f"[UGC] Отправляем видео пользователю...")
            
            # Отправляем видео (используем presigned URL если есть, иначе локальный файл)
            if video_url:
                await c.message.answer_video(
                    video_url, 
                    caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)"
                )
                logger.info(f"[UGC] ✅ Видео отправлено через R2 URL")
            else:
                await c.message.answer_video(
                    FSInputFile(video_path), 
                    caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)"
                )
                logger.info(f"[UGC] ✅ Видео отправлено через локальный файл")
            
            # Сохраняем генерацию в историю
            try:
                from tg_bot.utils.user_storage import save_user_generation
                logger.info(f"[UGC] Сохраняем генерацию в историю...")
                logger.info(f"[UGC] User ID: {c.from_user.id}")
                logger.info(f"[UGC] R2 Video Key: {r2_video_key}")
                logger.info(f"[UGC] Character: {get_character_gender(c.from_user.id)}/{get_character_age(c.from_user.id)}")
                logger.info(f"[UGC] Text: {get_character_text(c.from_user.id)}")
                
                generation_id = save_user_generation(
                    user_id=c.from_user.id,
                    generation_type='video',
                    r2_video_key=r2_video_key,
                    r2_audio_key=None,  # Аудио включено в MP4, не сохраняем отдельно
                    character_gender=get_character_gender(c.from_user.id),
                    character_age=get_character_age(c.from_user.id),
                    text_prompt=get_character_text(c.from_user.id),
                    credits_spent=COST_UGC_VIDEO
                )
                logger.info(f"[UGC] ✅ Генерация сохранена в историю с ID: {generation_id}")
            except Exception as save_error:
                logger.info(f"[UGC] ⚠️ Не удалось сохранить генерацию в историю: {save_error}")
                import traceback
                traceback.print_exc()
            
            # Сохраняем информацию об исходном видео для возможности монтажа
            set_original_video(c.from_user.id, r2_video_key, video_url)
            logger.info(f"[UGC] ✅ Сохранена информация об исходном видео для монтажа")
            
            # Удаляем видео файл после отправки
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                    logger.info(f"[UGC] ✅ Видео файл удален: {video_path}")
            except Exception as cleanup_error:
                logger.info(f"[UGC] ⚠️ Не удалось удалить видео файл: {cleanup_error}")
            
            # Очищаем временные отредактированные изображения персонажа
            try:
                edited_path = get_edited_character_path(c.from_user.id)
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
                clear_edit_session(c.from_user.id)
                logger.info(f"[UGC] ✅ Сессия редактирования очищена")
            except Exception as cleanup_error:
                logger.info(f"[UGC] ⚠️ Не удалось очистить временные файлы редактирования: {cleanup_error}")
            
            # Предлагаем монтаж или завершение
            await state.set_state(UGCCreation.waiting_editing_decision)
            await c.message.answer(
                "✨ Хочешь смонтировать видео?\n\n"
                "🎬 <b>Монтаж</b> - добавить субтитры и эффекты\n"
                "✅ <b>Завершить</b> - оставить как есть",
                reply_markup=video_editing_menu(),
                parse_mode="HTML"
            )
            logger.info(f"[UGC] Предложен выбор: монтаж или завершить")
        else:
            # Авто-рефанд если видео не получено
            add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise Exception("Видео не было сгенерировано")
        
    except Exception as e:
        logger.info(f"[UGC] ❌ Критическая ошибка при создании UGC рекламы: {e}")
        import traceback
        traceback.print_exc()
        
        # Очищаем временные файлы редактирования при ошибке
        try:
            edited_path = get_edited_character_path(c.from_user.id)
            if edited_path and os.path.exists(edited_path):
                os.remove(edited_path)
                logger.info(f"[UGC] ✅ Временное отредактированное изображение удалено при ошибке: {edited_path}")
            clear_edit_session(c.from_user.id)
            logger.info(f"[UGC] ✅ Сессия редактирования очищена при ошибке")
        except Exception as cleanup_error:
            logger.info(f"[UGC] ⚠️ Не удалось очистить временные файлы при ошибке: {cleanup_error}")
        
        # Скрываем технические ошибки от пользователей
        error_message = "❌ Произошла ошибка при создании видео"
        if "Exhausted balance" in str(e) or "User is locked" in str(e) or "TTS service temporarily unavailable" in str(e):
            error_message += "\n\n🔧 Сервис временно недоступен. Попробуй позже."
        elif "заблокировано системой безопасности" in str(e) or "content_policy_violation" in str(e):
            # Возвращаем кредит
            add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_content_policy_violation")
            
            logger.info(f"[UGC] 🚫 Блокировка системы безопасности - возвращаем к редактированию персонажа")
            
            # Получаем текущего персонажа для отображения
            from tg_bot.keyboards import character_editing_choice_menu
            
            gender = get_character_gender(c.from_user.id)
            character_idx = get_selected_character(c.from_user.id)
            
            # Отправляем сообщение о нарушении правил
            await c.message.answer(
                "🚫 <b>Кажется, создаваемое видео нарушает правила площадки</b>\n\n"
                "❗️ Изображение персонажа было заблокировано системой безопасности.\n\n"
                "💡 Попробуй изменить персонажа с помощью редактирования или выбери другого:",
                parse_mode="HTML"
            )
            
            # Показываем текущего персонажа
            if gender and character_idx is not None:
                character_data = get_character_image(gender, character_idx)
                if character_data:
                    character_path, age = character_data
                    try:
                        # Отправляем изображение персонажа с предложением редактирования
                        await c.message.answer_photo(
                            FSInputFile(character_path),
                            caption="🎨 <b>Хочешь отредактировать этого персонажа?</b>\n\n"
                                    "Ты можешь изменить внешность, одежду или окружение.\n\n"
                                    "Или выбери другого персонажа из галереи.",
                            reply_markup=character_editing_choice_menu(),
                            parse_mode="HTML"
                        )
                        await state.set_state(UGCCreation.waiting_editing_choice)
                        await c.answer()
                        return
                    except Exception as photo_error:
                        logger.error(f"[UGC] Не удалось отправить фото персонажа: {photo_error}")
            
            # Если не удалось показать персонажа, возвращаем к выбору
            from tg_bot.keyboards import gender_selection_menu
            await c.message.answer(
                "Выбери персонажа:",
                reply_markup=gender_selection_menu()
            )
            await state.set_state(UGCCreation.waiting_gender_selection)
            await c.answer()
            return
        else:
            if "API" in str(e) or "fal.ai" in str(e) or "TTS service error" in str(e):
                error_message += "\n\n🔧 Проблема с сервисом генерации. Попробуй позже."
            else:
                error_message += "\n\nПопробуй еще раз или свяжись с администратором."
            
            await c.message.answer(
                error_message,
                reply_markup=main_menu()
            )
            await state.clear()
            await c.answer()
