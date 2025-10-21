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

from tg_bot.states import UGCCreation
from tg_bot.utils.credits import get_credits, spend_credits, add_credits
from tg_bot.utils.constants import COST_UGC_VIDEO
from tg_bot.utils.user_state import (
    get_selected_character, get_character_text, set_character_text,
    get_selected_voice, get_last_audio, set_last_audio,
    get_character_gender, get_character_age,
    get_original_character_path, get_edited_character_path,
    clear_edit_session
)
from tg_bot.utils.files import get_character_image
from tg_bot.utils.audio import check_audio_duration_limit
from tg_bot.services.elevenlabs_service import tts_to_file
from tg_bot.services.falai_service import generate_talking_head_video
from tg_bot.services.r2_service import download_file, delete_file
from tg_bot.keyboards import (
    audio_confirmation_menu, text_change_decision_menu,
    back_to_main_menu, main_menu
)
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "audio_confirmed")
async def audio_confirmed(c: CallbackQuery, state: FSMContext):
    """Пользователь подтвердил аудио, сразу начинаем генерацию видео"""
    
    def log(msg):
        """Логирование с принудительным flush"""
        logger.info(msg)
        sys.stdout.flush()
    
    # Отвечаем на callback query сразу, чтобы избежать timeout
    await c.answer()
    
    log(f"[UGC] User {c.from_user.id} подтвердил аудио, начинаем генерацию видео")
    
    # Проверяем кредиты
    credits = get_credits(c.from_user.id)
    if credits < COST_UGC_VIDEO:
        log(f"[UGC] Недостаточно кредитов у user {c.from_user.id}")
        await c.message.answer(
            f"❌ Недостаточно кредитов (нужно {COST_UGC_VIDEO} кредит).\n\n"
            "Свяжись с администратором для пополнения.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    # Списываем кредит
    ok = spend_credits(c.from_user.id, COST_UGC_VIDEO, "ugc_video_creation")
    if not ok:
        log(f"[UGC] Не удалось списать кредит у user {c.from_user.id}")
        await c.message.answer(
            "❌ Ошибка при списании кредита.\n\n"
            "Свяжись с администратором.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    log(f"[UGC] Кредит списан успешно")
    
    try:
        await c.message.answer("⏳ Начинаю создание UGC рекламы...\n\nЭто займет несколько минут.")
        log(f"[UGC] Стартовое сообщение отправлено")
        
        # Получаем сохраненные данные
        log(f"[UGC] Получаем сохраненные данные...")
        character_idx = get_selected_character(c.from_user.id)
        character_text = get_character_text(c.from_user.id)
        audio_path = get_last_audio(c.from_user.id)
        
        # Получаем параметры персонажа
        gender = get_character_gender(c.from_user.id)
        age = get_character_age(c.from_user.id)
        
        log(f"[UGC] Данные получены: character_idx={character_idx}, gender={gender}, age={age}")
        log(f"[UGC] Текст: {character_text[:30] if character_text else 'None'}...")
        log(f"[UGC] Аудио: {audio_path}")
        
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
                    log(f"[UGC] Используем отредактированную версию из R2: {edited_character_path}")
                else:
                    log(f"[UGC] Не удалось скачать из R2, используем оригинал")
                    selected_frame = get_character_image(gender, age, character_idx)
            else:
                # Legacy local path support
                if os.path.exists(edited_character_path):
                    selected_frame = edited_character_path
                    log(f"[UGC] Используем локальную отредактированную версию: {edited_character_path}")
                else:
                    log(f"[UGC] Файл не найден, используем оригинал")
                    selected_frame = get_character_image(gender, age, character_idx)
        else:
            # No edited version
            selected_frame = get_character_image(gender, age, character_idx)
            log(f"[UGC] Используем оригинальную систему персонажей: {gender}/{age}, индекс {character_idx}")
        
        if not selected_frame:
            log(f"[UGC] ❌ Кадр не найден!")
            if gender and age:
                raise Exception(f"Не удалось найти персонажа с параметрами: пол={gender}, возраст={age}, индекс={character_idx}")
            else:
                raise Exception("Не удалось найти выбранный кадр")
        
        if not audio_path or not os.path.exists(audio_path):
            log(f"[UGC] ❌ Аудио не найдено!")
            raise Exception("Не удалось найти аудио файл")
        
        log(f"[UGC] Выбран кадр: {selected_frame}")
        
        # Генерируем видео с помощью fal.ai OmniHuman
        # Передаем стартовый кадр персонажа и аудио
        await c.message.answer("🎬 Создаю UGC рекламу с синхронизацией губ... (это может занять 2-3 минуты)")
        log(f"[UGC] Начинаем генерацию talking head видео через fal.ai...")
        log(f"[UGC] Стартовый кадр: {selected_frame}")
        log(f"[UGC] Аудио файл: {audio_path}")
        
        try:
            log(f"[UGC] Calling generate_talking_head_video with user_id: {c.from_user.id}")
            video_result = await generate_talking_head_video(
                audio_path=audio_path,
                image_path=selected_frame,
                user_id=c.from_user.id
            )
            
            if not video_result:
                raise Exception("Не удалось сгенерировать видео")
            
            video_path = video_result['local_path']
            video_url = video_result.get('video_url')
            r2_video_key = video_result.get('r2_video_key')
            # r2_audio_key всегда None - аудио включено в MP4
            
            log(f"[UGC] Видео сгенерировано: {video_path}")
            log(f"[UGC] Video URL: {video_url}")
            log(f"[UGC] R2 Video Key: {r2_video_key}")
            if r2_video_key:
                log(f"[UGC] Видео сохранено в R2: {r2_video_key}")
            else:
                log(f"[UGC] ⚠️ R2 Video Key is None - video not saved to R2")
        except Exception as video_error:
            log(f"[UGC] ❌ Ошибка при генерации видео: {video_error}")
            import traceback
            traceback.print_exc()
            # Авто-рефанд кредита при неуспехе генерации
            add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise Exception(f"Ошибка генерации видео: {str(video_error)}")
        
        if video_path:
            await c.message.answer("✅ Отправляю готовое видео...")
            log(f"[UGC] Отправляем видео пользователю...")
            
            # Отправляем видео (используем presigned URL если есть, иначе локальный файл)
            if video_url:
                await c.message.answer_video(
                    video_url, 
                    caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)"
                )
                log(f"[UGC] ✅ Видео отправлено через R2 URL")
            else:
                await c.message.answer_video(
                    FSInputFile(video_path), 
                    caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)"
                )
                log(f"[UGC] ✅ Видео отправлено через локальный файл")
            
            # Сохраняем генерацию в историю
            try:
                from tg_bot.utils.user_storage import save_user_generation
                log(f"[UGC] Сохраняем генерацию в историю...")
                log(f"[UGC] User ID: {c.from_user.id}")
                log(f"[UGC] R2 Video Key: {r2_video_key}")
                log(f"[UGC] Character: {get_character_gender(c.from_user.id)}/{get_character_age(c.from_user.id)}")
                log(f"[UGC] Text: {get_character_text(c.from_user.id)}")
                
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
                log(f"[UGC] ✅ Генерация сохранена в историю с ID: {generation_id}")
            except Exception as save_error:
                log(f"[UGC] ⚠️ Не удалось сохранить генерацию в историю: {save_error}")
                import traceback
                traceback.print_exc()
            
            # Удаляем видео файл после отправки
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                    log(f"[UGC] ✅ Видео файл удален: {video_path}")
            except Exception as cleanup_error:
                log(f"[UGC] ⚠️ Не удалось удалить видео файл: {cleanup_error}")
            
            # Очищаем временные отредактированные изображения персонажа
            try:
                edited_path = get_edited_character_path(c.from_user.id)
                if edited_path:
                    # Check if it's R2 key or local path
                    if edited_path.startswith("users/"):
                        # It's R2 key - delete from R2
                        if delete_file(edited_path):
                            log(f"[UGC] ✅ Отредактированное изображение удалено из R2: {edited_path}")
                        else:
                            log(f"[UGC] ⚠️ Не удалось удалить из R2: {edited_path}")
                    else:
                        # Legacy local path
                        if os.path.exists(edited_path):
                            os.remove(edited_path)
                            log(f"[UGC] ✅ Локальное отредактированное изображение удалено: {edited_path}")
                    
                    # Also delete temp file if downloaded from R2
                    if temp_edited_path and os.path.exists(temp_edited_path):
                        os.remove(temp_edited_path)
                        log(f"[UGC] ✅ Временный файл удален: {temp_edited_path}")
                
                # Очищаем сессию редактирования
                clear_edit_session(c.from_user.id)
                log(f"[UGC] ✅ Сессия редактирования очищена")
            except Exception as cleanup_error:
                log(f"[UGC] ⚠️ Не удалось очистить временные файлы редактирования: {cleanup_error}")
        else:
            # Авто-рефанд если видео не получено
            add_credits(c.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise Exception("Видео не было сгенерировано")
        
        # Очищаем состояние
        await state.clear()
        log(f"[UGC] Состояние очищено")
        
        # Предлагаем создать еще одно видео
        await c.message.answer(
            "🎬 Хочешь создать еще одну UGC рекламу?",
            reply_markup=main_menu()
        )
        
    except Exception as e:
        log(f"[UGC] ❌ Критическая ошибка при создании UGC рекламы: {e}")
        import traceback
        traceback.print_exc()
        
        # Очищаем временные файлы редактирования при ошибке
        try:
            edited_path = get_edited_character_path(c.from_user.id)
            if edited_path and os.path.exists(edited_path):
                os.remove(edited_path)
                log(f"[UGC] ✅ Временное отредактированное изображение удалено при ошибке: {edited_path}")
            clear_edit_session(c.from_user.id)
            log(f"[UGC] ✅ Сессия редактирования очищена при ошибке")
        except Exception as cleanup_error:
            log(f"[UGC] ⚠️ Не удалось очистить временные файлы при ошибке: {cleanup_error}")
        
        await c.message.answer(
            f"❌ Произошла ошибка при создании видео:\n\n{str(e)}\n\n"
            "Попробуй еще раз или свяжись с администратором.",
            reply_markup=main_menu()
        )
        await state.clear()


@dp.callback_query(F.data == "audio_redo")
async def audio_redo(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет переделать аудио"""
    await c.message.answer(
        "🔄 Хочешь изменить текст или просто перегенерировать аудио с тем же текстом?",
        reply_markup=text_change_decision_menu()
    )
    await state.set_state(UGCCreation.waiting_text_change_decision)
    await c.answer()


@dp.callback_query(F.data == "change_text_yes")
async def change_text_yes(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет изменить текст"""
    await c.message.answer(
        "✏️ Отлично! Напиши новый текст для персонажа.\n\n"
        "⚠️ <b>Важно:</b> Текст должен быть таким, чтобы озвучка заняла не более 15 секунд!",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    await state.set_state(UGCCreation.waiting_new_character_text)
    await c.answer()


@dp.callback_query(F.data == "change_text_no")
async def change_text_no(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет перегенерировать с тем же текстом"""
    # Получаем сохраненный текст
    character_text = get_character_text(c.from_user.id)
    
    if not character_text:
        await c.message.answer(
            "❌ Не найден предыдущий текст. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return await c.answer()
    
    voice_id = get_selected_voice(c.from_user.id)
    
    if not voice_id:
        await c.message.answer(
            "❌ Голос не выбран. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return await c.answer()
    
    try:
        await c.message.answer("🎤 Перегенерирую озвучку с тем же текстом...")
        logger.info(f"[UGC] Перегенерация TTS для пользователя {c.from_user.id}, voice_id={voice_id}")
        
        # Удаляем старое аудио если есть
        old_audio_path = get_last_audio(c.from_user.id)
        if old_audio_path and os.path.exists(old_audio_path):
            try:
                os.remove(old_audio_path)
            except:
                pass
        
        audio_path = await tts_to_file(character_text, voice_id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        logger.info(f"[UGC] Аудио перегенерировано: {audio_path}")
        
        # Сохраняем путь к новому аудио
        set_last_audio(c.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        logger.info(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            await c.message.answer(
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
            return await c.answer()
        
        # Отправляем новое аудио
        await c.message.answer_audio(
            FSInputFile(audio_path),
            caption=f"🎤 Новая версия озвучки ({duration:.1f} сек)"
        )
        
        # Снова даем возможность подтвердить или переделать
        await c.message.answer(
            "✅ Озвучка готова! Что будем делать?",
            reply_markup=audio_confirmation_menu()
        )
        
        await state.set_state(UGCCreation.waiting_audio_confirmation)
        
    except Exception as e:
        logger.error(f"[UGC] Ошибка при перегенерации аудио: {e}")
        import traceback
        traceback.print_exc()
        
        await c.message.answer(
            "❌ Произошла ошибка при генерации озвучки.\n\n"
            "Попробуй еще раз или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
        await state.clear()
    
    await c.answer()


@dp.message(F.text, UGCCreation).waiting_character_text
async def character_text_received(m: Message, state: FSMContext):
    """Получен текст от пользователя для генерации аудио"""
    # Сохраняем текст
    set_character_text(m.from_user.id, m.text)
    logger.info(f"User {m.from_user.id} ввел текст персонажа: {m.text[:50]}...")
    
    # Получаем выбранный голос
    voice_id = get_selected_voice(m.from_user.id)
    
    if not voice_id:
        await m.answer(
            "❌ Голос не выбран. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    try:
        # Генерируем аудио напрямую из текста пользователя
        await m.answer("🎤 Генерирую озвучку...")
        logger.info(f"[UGC] Генерация TTS для пользователя {m.from_user.id}, voice_id={voice_id}")
        
        audio_path = await tts_to_file(m.text, voice_id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        logger.info(f"[UGC] Аудио сгенерировано: {audio_path}")
        
        # Сохраняем путь к аудио
        set_last_audio(m.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        logger.info(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
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
            return
        
        # Отправляем сгенерированное аудио для прослушивания
        await m.answer_audio(
            FSInputFile(audio_path),
            caption=f"🎤 Вот как это будет звучать ({duration:.1f} сек)"
        )
        
        # Даем возможность подтвердить или переделать аудио
        await m.answer(
            "✅ Озвучка готова! Что будем делать?",
            reply_markup=audio_confirmation_menu()
        )
        
        await state.set_state(UGCCreation.waiting_audio_confirmation)
        
    except Exception as e:
        logger.error(f"[UGC] Ошибка при генерации аудио: {e}")
        import traceback
        traceback.print_exc()
        
        await m.answer(
            "❌ Произошла ошибка при генерации озвучки.\n\n"
            "Попробуй еще раз или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
        await state.clear()


@dp.message(F.text, UGCCreation).waiting_new_character_text
async def new_character_text_received(m: Message, state: FSMContext):
    """Получен новый текст для переделки аудио"""
    # Сохраняем новый текст
    set_character_text(m.from_user.id, m.text)
    logger.info(f"User {m.from_user.id} ввел новый текст персонажа: {m.text[:50]}...")
    
    # Получаем выбранный голос
    voice_id = get_selected_voice(m.from_user.id)
    
    if not voice_id:
        await m.answer(
            "❌ Голос не выбран. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    try:
        await m.answer("🎤 Генерирую новую озвучку...")
        logger.info(f"[UGC] Генерация нового TTS для пользователя {m.from_user.id}, voice_id={voice_id}")
        
        # Удаляем старое аудио если есть
        old_audio_path = get_last_audio(m.from_user.id)
        if old_audio_path and os.path.exists(old_audio_path):
            try:
                os.remove(old_audio_path)
            except:
                pass
        
        audio_path = await tts_to_file(m.text, voice_id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        logger.info(f"[UGC] Новое аудио сгенерировано: {audio_path}")
        
        # Сохраняем путь к аудио
        set_last_audio(m.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        logger.info(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
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
            return
        
        # Отправляем сгенерированное аудио для прослушивания
        await m.answer_audio(
            FSInputFile(audio_path),
            caption=f"🎤 Вот как это будет звучать ({duration:.1f} сек)"
        )
        
        # Даем возможность подтвердить или переделать аудио
        await m.answer(
            "✅ Озвучка готова! Что будем делать?",
            reply_markup=audio_confirmation_menu()
        )
        
        await state.set_state(UGCCreation.waiting_audio_confirmation)
        
    except Exception as e:
        logger.error(f"[UGC] Ошибка при генерации нового аудио: {e}")
        import traceback
        traceback.print_exc()
        
        await m.answer(
            "❌ Произошла ошибка при генерации озвучки.\n\n"
            "Попробуй еще раз или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
        await state.clear()
