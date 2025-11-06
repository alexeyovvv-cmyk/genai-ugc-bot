"""Generation handlers for the Telegram bot.

This module contains handlers for:
- Fully automated UGC video creation flow
- Text enhancement with emotion analysis
- Multi-segment TTS generation with emotions
- Audio concatenation
- Video generation
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
    set_original_video,
    set_cached_overlay_urls
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
    back_to_main_menu, main_menu, video_editing_menu
)
from tg_bot.config import BASE_DIR
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.message(StateFilter(UGCCreation.waiting_character_text), F.text)
async def character_text_received(m: Message, state: FSMContext):
    """Полностью автоматический флоу создания UGC рекламы"""
    set_character_text(m.from_user.id, m.text)
    logger.info(f"[GENERATION] User {m.from_user.id} entered text: {m.text[:100]}...")
    
    gender = get_character_gender(m.from_user.id)
    age = get_character_age(m.from_user.id)
    character_idx = get_selected_character(m.from_user.id)
    
    if not gender:
        await m.answer(
            "❌ Не выбраны параметры персонажа. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    try:
        # ШАГ 1: Обрабатываем текст и анализируем эмоции
        await m.answer("🤖 Обрабатываю текст и анализирую эмоции...")
        
        logger.info(f"[GENERATION] Starting prompt enhancement...")
        enhanced_text = await enhance_prompt(m.text)
        
        segments = parse_emotion_segments(enhanced_text)
        
        if not segments:
            logger.warning(f"[ENHANCEMENT] No segments parsed, using original text")
            segments = [{"emotion": DEFAULT_TTS_EMOTION, "text": m.text}]
        
        for segment in segments:
            segment['emotion'] = normalize_emotion(segment['emotion'])
        
        logger.info(f"[GENERATION] Parsed {len(segments)} emotion segments")
        
        # ШАГ 2: Показываем разбивку по эмоциям
        segments_text = "Разбивка по эмоциям:\n\n"
        for i, segment in enumerate(segments, 1):
            segments_text += f"{i}. [{segment['emotion']}] {segment['text']}\n\n"
        await m.answer(segments_text)
        
        # ШАГ 3: Проверяем и списываем кредиты
        credits = get_credits(m.from_user.id)
        if credits < COST_UGC_VIDEO:
            await m.answer(
                f"❌ Недостаточно кредитов (нужно {COST_UGC_VIDEO} кредит).\n\n"
                "Свяжись с администратором для пополнения.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
        
        ok = spend_credits(m.from_user.id, COST_UGC_VIDEO, "ugc_video_creation")
        if not ok:
            await m.answer(
                "❌ Ошибка при списании кредита.\n\nСвяжись с администратором.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
        
        # ШАГ 4: Генерируем озвучку
        await m.answer(f"🎤 Генерирую озвучку ({len(segments)} сегментов)...")
        
        voice_id = get_voice_for_character(gender, age)
        language = get_default_language()
        logger.info(f"[UGC] Автовыбор голоса: gender={gender}, voice_id={voice_id}")
        
        audio_paths = []
        for i, segment in enumerate(segments):
            logger.info(f"[GENERATION] Segment {i+1}/{len(segments)}: emotion={segment['emotion']}, text={segment['text'][:50]}...")
            
            try:
                audio_path = await tts_to_file(
                    text=segment['text'],
                    voice_id=voice_id,
                    language=language,
                    emotion=segment['emotion'],
                    user_id=m.from_user.id
                )
                
                if not audio_path:
                    raise Exception(f"Не удалось сгенерировать аудио для сегмента {i+1}")
                
                audio_paths.append(audio_path)
                
            except Exception as e:
                logger.error(f"[GENERATION] TTS failed for segment {i+1}: {e}")
                add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_tts_fail")
                await m.answer(
                    f"❌ Ошибка генерации аудио. Попробуйте позже.",
                    reply_markup=main_menu()
                )
                await state.clear()
                return
        
        logger.info(f"[GENERATION] All {len(audio_paths)} TTS segments generated successfully")
        
        # Склеиваем аудио
        timestamp = int(time.time())
        audio_dir = BASE_DIR / "data" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        final_audio_path = str(audio_dir / f"final_audio_{m.from_user.id}_{timestamp}.mp3")
        
        try:
            final_audio_path = await concatenate_audio_files(
                audio_paths=audio_paths,
                output_path=final_audio_path,
                pause_duration_ms=130
            )
            logger.info(f"[GENERATION] Audio concatenation completed: {final_audio_path}")
        except Exception as e:
            logger.error(f"[AUDIO_CONCAT] Concatenation failed: {e}")
            if audio_paths:
                final_audio_path = audio_paths[0]
                logger.warning(f"[AUDIO_CONCAT] Using first segment as fallback: {final_audio_path}")
            else:
                raise Exception("Не удалось сгенерировать аудио")
        
        audio_path = final_audio_path
        set_last_audio(m.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=30.0)
        logger.info(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_audio_too_long")
            await m.answer(
                f"❌ <b>Аудио слишком длинное!</b>\n\n"
                f"Длительность твоей озвучки: <b>{duration:.1f} секунд</b>\n"
                f"Максимум: <b>30 секунд</b>\n\n"
                f"Пожалуйста, сократи текст и попробуй снова.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            try:
                if os.path.exists(audio_path): os.remove(audio_path)
                for temp_path in audio_paths:
                    if os.path.exists(temp_path): os.remove(temp_path)
            except: pass
            await state.clear()
            return
        
        # ШАГ 5: Начинаем генерацию видео
        await m.answer("⏳ Начинаю создание UGC рекламы...\n\nЭто займет несколько минут.")
        logger.info(f"[UGC] Starting video generation")
        
        # Получаем изображение персонажа
        if not gender or not age or character_idx is None:
            raise Exception("Не выбраны параметры персонажа. Начните сначала.")
        
        edited_character_path = get_edited_character_path(m.from_user.id)
        temp_edited_path = None
        
        if edited_character_path:
            if edited_character_path.startswith("users/"):
                temp_edited_path = f"data/temp_edits/temp_{int(time.time())}.jpg"
                if download_file(edited_character_path, temp_edited_path):
                    selected_frame = temp_edited_path
                    logger.info(f"[UGC] Используем отредактированную версию из R2")
                else:
                    logger.info(f"[UGC] Не удалось скачать из R2, используем оригинал")
                    character_data = get_character_image(gender, character_idx)
                    selected_frame = character_data[0] if character_data else None
            else:
                if os.path.exists(edited_character_path):
                    selected_frame = edited_character_path
                    logger.info(f"[UGC] Используем локальную отредактированную версию")
                else:
                    logger.info(f"[UGC] Файл не найден, используем оригинал")
                    character_data = get_character_image(gender, character_idx)
                    selected_frame = character_data[0] if character_data else None
        else:
            character_data = get_character_image(gender, character_idx)
            if character_data:
                selected_frame, detected_age = character_data
                logger.info(f"[UGC] Используем оригинальную систему персонажей")
            else:
                selected_frame = None
        
        if not selected_frame:
            logger.info(f"[UGC] ❌ Кадр не найден!")
            raise Exception(f"Не удалось найти персонажа")
        
        logger.info(f"[UGC] Генерируем talking head видео через fal.ai...")
        
        try:
            video_result = await generate_talking_head_video(
                audio_path=audio_path,
                image_path=selected_frame,
                user_id=m.from_user.id
            )
            
            if not video_result:
                raise Exception("Не удалось сгенерировать видео")
            
            video_path = video_result['local_path']
            video_url = video_result.get('video_url')
            r2_video_key = video_result.get('r2_video_key')
            
            # Очищаем кеш оверлеев при генерации нового видео
            set_cached_overlay_urls(m.from_user.id, {}, {})
            
            logger.info(f"[UGC] Видео сгенерировано успешно")
            
        except Exception as video_error:
            logger.error(f"[UGC] ❌ Ошибка при генерации видео: {video_error}")
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise video_error
        
        # ШАГ 6: Отправляем готовое видео
        if video_path:
            await m.answer("✅ Отправляю готовое видео...")
            
            if video_url:
                await m.answer_video(video_url, caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)")
            else:
                await m.answer_video(FSInputFile(video_path), caption=f"🎉 Твоя UGC реклама готова!\n\n(-{COST_UGC_VIDEO} кредит списан)")
            
            logger.info(f"[UGC] ✅ Видео отправлено пользователю")
            
            # Сохраняем в историю
            try:
                from tg_bot.utils.user_storage import save_user_generation
                generation_id = save_user_generation(
                    user_id=m.from_user.id,
                    generation_type='video',
                    r2_video_key=r2_video_key,
                    r2_audio_key=None,
                    character_gender=gender,
                    character_age=age,
                    text_prompt=get_character_text(m.from_user.id),
                    credits_spent=COST_UGC_VIDEO
                )
                logger.info(f"[UGC] ✅ Генерация сохранена в историю: {generation_id}")
            except Exception as save_error:
                logger.warning(f"[UGC] ⚠️ Не удалось сохранить в историю: {save_error}")
            
            set_original_video(m.from_user.id, r2_video_key, video_url)
            
            # Очистка файлов
            try:
                if os.path.exists(audio_path): os.remove(audio_path)
                if os.path.exists(video_path): os.remove(video_path)
                for temp_path in audio_paths:
                    if os.path.exists(temp_path): os.remove(temp_path)
                logger.info(f"[UGC] ✅ Временные файлы удалены")
            except: pass
            
            # Очистка отредактированного персонажа
            try:
                if edited_character_path:
                    if edited_character_path.startswith("users/"):
                        delete_file(edited_character_path)
                    else:
                        if os.path.exists(edited_character_path):
                            os.remove(edited_character_path)
                    if temp_edited_path and os.path.exists(temp_edited_path):
                        os.remove(temp_edited_path)
                clear_edit_session(m.from_user.id)
            except: pass
            
            # Предлагаем монтаж
            await state.set_state(UGCCreation.waiting_editing_decision)
            await m.answer(
                "✨ Хочешь смонтировать видео?\n\n"
                "🎬 <b>Монтаж</b> - добавить субтитры и эффекты\n"
                "✅ <b>Завершить</b> - оставить как есть",
                reply_markup=video_editing_menu(),
                parse_mode="HTML"
            )
        else:
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_ugc_fail")
            raise Exception("Видео не было сгенерировано")
        
    except Exception as e:
        logger.error(f"[UGC] ❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Очистка при ошибке
        try:
            edited_path = get_edited_character_path(m.from_user.id)
            if edited_path and os.path.exists(edited_path):
                os.remove(edited_path)
            clear_edit_session(m.from_user.id)
        except: pass
        
        error_message = "❌ Произошла ошибка при создании видео"
        
        if "Exhausted balance" in str(e) or "User is locked" in str(e) or "TTS service temporarily unavailable" in str(e):
            error_message += "\n\n🔧 Сервис временно недоступен. Попробуй позже."
        elif "заблокировано системой безопасности" in str(e) or "content_policy_violation" in str(e):
            add_credits(m.from_user.id, COST_UGC_VIDEO, "refund_content_policy_violation")
            from tg_bot.keyboards import character_editing_choice_menu, gender_selection_menu
            
            await m.answer(
                "🚫 <b>Изображение заблокировано системой безопасности</b>\n\n"
                "💡 Попробуй выбрать или отредактировать другого персонажа:",
                parse_mode="HTML"
            )
            
            if gender and character_idx is not None:
                character_data = get_character_image(gender, character_idx)
                if character_data:
                    character_path, age = character_data
                    try:
                        await m.answer_photo(
                            FSInputFile(character_path),
                            caption="🎨 <b>Отредактировать персонажа?</b>",
                            reply_markup=character_editing_choice_menu(),
                            parse_mode="HTML"
                        )
                        await state.set_state(UGCCreation.waiting_editing_choice)
                        return
                    except: pass
            
            await m.answer("Выбери персонажа:", reply_markup=gender_selection_menu())
            await state.set_state(UGCCreation.waiting_gender_selection)
            return
        else:
            if "API" in str(e) or "fal.ai" in str(e) or "TTS service error" in str(e):
                error_message += "\n\n🔧 Проблема с сервисом генерации. Попробуй позже."
            else:
                error_message += "\n\nПопробуй еще раз или свяжись с администратором."
        
        await m.answer(error_message, reply_markup=main_menu())
        await state.clear()
