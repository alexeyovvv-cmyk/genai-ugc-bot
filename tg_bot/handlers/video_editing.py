"""
Handlers for video editing functionality.

This module handles:
- Video editing (subtitles, compositing)
- Finishing generation flow without editing
- Re-editing support (multiple iterations)
- Resume editing after bot restart
"""
import copy
import json
import logging
import re
from typing import Sequence

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter, Command

from tg_bot.states import UGCCreation, RenderEditing
from tg_bot.keyboards import main_menu, video_editing_menu, render_settings_menu
from tg_bot.utils.user_state import (
    get_original_video,
    get_last_generated_video,
    set_last_generated_video,
    clear_all_video_data,
    get_video_format,
    get_background_video_path,
    get_character_text,
    set_cached_overlay_urls
)
from tg_bot.services.video_editing_service import (
    add_subtitles_to_video,
    composite_head_with_background,
    get_render_session_summary,
    rerender_last_render_session,
    VideoEditingError
)
from tg_bot.dispatcher import dp
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

ALLOWED_TEMPLATES = [
    "overlay",
    "circle",
    "basic",
    "mix_basic_overlay",
    "mix_basic_circle",
]
TEMPLATE_FALLBACK = ["mix_basic_circle"]
DEFAULT_SUBTITLE_THEME = "light"
DEFAULT_INTRO_LENGTH = 2.5


def _is_cancel_text(text: str) -> bool:
    return text.strip().lower() in {"cancel", "отмена", "стоп"}


def _normalize_templates(raw) -> list[str]:
    if not raw:
        return list(TEMPLATE_FALLBACK)
    templates = []
    for item in raw:
        item = (item or "").strip()
        if item in ALLOWED_TEMPLATES and item not in templates:
            templates.append(item)
    return templates or list(TEMPLATE_FALLBACK)


def _normalize_subtitle_settings(settings: dict | None) -> dict:
    data = {
        "mode": "auto",
        "theme": DEFAULT_SUBTITLE_THEME,
        "transcript": None,
        "file_r2_key": None,
    }
    if settings:
        data.update({k: v for k, v in settings.items() if v is not None})
    return data


def _normalize_clip_settings(settings: dict | None) -> dict:
    data = {
        "enabled": False,
        "url": None,
        "length": DEFAULT_INTRO_LENGTH,
        "templates": None,
    }
    if settings:
        data.update(settings)
    return data


def _normalize_circle_settings(settings: dict | None) -> dict:
    data = {
        "radius": 0.35,
        "center_x": 0.5,
        "center_y": 0.5,
        "auto_center": True,
    }
    if settings:
        data.update(settings)
    return data


def _build_overrides_from_summary(summary: dict) -> dict:
    return {
        "templates": _normalize_templates(summary.get("templates")),
        "subtitles": _normalize_subtitle_settings(summary.get("subtitle_settings")),
        "intro": _normalize_clip_settings(summary.get("intro_settings")),
        "outro": _normalize_clip_settings(summary.get("outro_settings")),
        "circle": _normalize_circle_settings(summary.get("circle_settings")),
    }


def _format_render_summary(overrides: dict) -> str:
    subtitles = overrides["subtitles"]
    intro = overrides["intro"]
    outro = overrides["outro"]
    circle = overrides["circle"]
    intro_desc = "вкл" if intro.get("enabled") else "выкл"
    outro_desc = "вкл" if outro.get("enabled") else "выкл"
    templates = ", ".join(overrides["templates"]) or "—"
    circle_desc = (
        f"r={circle.get('radius', 0.35):.2f}, "
        f"x={circle.get('center_x', 0.5):.2f}, "
        f"y={circle.get('center_y', 0.5):.2f}"
    )
    return (
        "⚙️ <b>Текущие настройки рендера</b>\n"
        f"• Шаблоны: {templates}\n"
        f"• Субтитры: {subtitles.get('mode', 'auto')} (тема: {subtitles.get('theme', DEFAULT_SUBTITLE_THEME)})\n"
        f"• Интро: {intro_desc}\n"
        f"• Аутро: {outro_desc}\n"
        f"• Circle: {circle_desc}"
    )


async def _send_render_settings_message(target_message: Message, overrides: dict) -> None:
    text = _format_render_summary(overrides)
    await target_message.answer(text, reply_markup=render_settings_menu(), parse_mode="HTML")


def _video_menu_for_user(user_id: int):
    has_session = get_render_session_summary(user_id) is not None
    return video_editing_menu(has_session)


async def _start_render_editing_flow(msg_or_cb_message: Message, user_id: int, state: FSMContext) -> None:
    summary = get_render_session_summary(user_id)
    if not summary:
        await msg_or_cb_message.answer("ℹ️ Пока нет готового рендера для настроек. Сначала запусти монтаж.")
        return
    overrides = _build_overrides_from_summary(summary)
    await state.set_state(RenderEditing.choosing_action)
    await state.update_data(render_overrides=copy.deepcopy(overrides))
    await _send_render_settings_message(msg_or_cb_message, overrides)


def _get_overrides_from_state(data: dict) -> dict:
    overrides = data.get("render_overrides")
    if not overrides:
        overrides = _build_overrides_from_summary({})
    return overrides


async def _store_overrides(state: FSMContext, overrides: dict) -> None:
    await state.update_data(render_overrides=copy.deepcopy(overrides))


async def _back_to_render_menu(message: Message, state: FSMContext, overrides: dict) -> None:
    await state.set_state(RenderEditing.choosing_action)
    await _send_render_settings_message(message, overrides)


def _parse_clip_settings(
    text: str,
    default_templates: Sequence[str],
) -> dict:
    text = text.strip()
    if text.lower() == "off":
        return {
            "enabled": False,
            "url": None,
            "length": DEFAULT_INTRO_LENGTH,
            "templates": None,
        }
    parts = text.split()
    if len(parts) < 2:
        raise ValueError("Нужно указать URL и длительность.")
    url = parts[0]
    try:
        length = float(parts[1])
    except ValueError as exc:
        raise ValueError("Длительность должна быть числом.") from exc
    templates = default_templates
    if len(parts) >= 3:
        raw_templates = [item.strip() for item in re.split(r"[,\s]+", parts[2]) if item.strip()]
        valid_templates = [item for item in raw_templates if item in ALLOWED_TEMPLATES]
        if not valid_templates:
            raise ValueError("Не удалось распознать шаблоны для клипа.")
        templates = valid_templates
    return {
        "enabled": True,
        "url": url,
        "length": length,
        "templates": templates,
    }


def _parse_circle_settings(text: str, current: dict) -> dict:
    parts = text.split()
    if len(parts) < 3:
        raise ValueError("Нужно указать radius, center_x и center_y.")
    try:
        radius = float(parts[0])
        center_x = float(parts[1])
        center_y = float(parts[2])
    except ValueError as exc:
        raise ValueError("Все значения должны быть числом.") from exc
    if not (0.05 <= radius <= 0.6):
        raise ValueError("Radius должен быть в диапазоне 0.05-0.6.")
    if not (0.0 <= center_x <= 1.0 and 0.0 <= center_y <= 1.0):
        raise ValueError("center_x/center_y должны быть в диапазоне 0-1.")
    auto_center = current.get("auto_center", True)
    if len(parts) >= 4:
        mode = parts[3].lower()
        if mode == "auto":
            auto_center = True
        elif mode == "manual":
            auto_center = False
        else:
            raise ValueError("Последний параметр должен быть auto или manual.")
    updated = dict(current)
    updated.update(
        {
            "radius": radius,
            "center_x": center_x,
            "center_y": center_y,
            "auto_center": auto_center,
        }
    )
    return updated


@dp.message(Command("renderinfo"))
async def render_info_command(m: Message, state: FSMContext) -> None:
    summary = get_render_session_summary(m.from_user.id)
    if not summary:
        await m.answer("ℹ️ Пока нет готовых рендеров для просмотра.")
        return

    subtitles = summary.get("subtitle_settings") or {}
    intro_settings = summary.get("intro_settings") or {}
    outro_settings = summary.get("outro_settings") or {}
    circle_settings = summary.get("circle_settings") or {}
    message = (
        "📋 <b>Последний рендер</b>\n"
        f"• Статус: {summary.get('status', 'unknown')}\n"
        f"• Шаблоны: {', '.join(summary.get('templates') or []) or '—'}\n"
        f"• Субтитры: {subtitles.get('mode', 'auto')} (тема: {subtitles.get('theme', 'light')})\n"
        f"• Интро: {'вкл' if intro_settings.get('enabled') else 'выкл'}\n"
        f"• Аутро: {'вкл' if outro_settings.get('enabled') else 'выкл'}\n"
        f"• Круг: r={circle_settings.get('radius', '0.35')} "
        f"({circle_settings.get('center_x', '0.5')}, {circle_settings.get('center_y', '0.5')})\n"
        f"• Result URL: {summary.get('result_url') or '—'}"
    )
    await m.answer(message, parse_mode="HTML")


@dp.message(Command("rerender"))
async def rerender_command(m: Message, state: FSMContext) -> None:
    text = m.text or ""
    overrides = {}
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        try:
            overrides = json.loads(parts[1])
        except json.JSONDecodeError:
            await m.answer("❌ Не удалось распарсить JSON с настройками. Отправь корректный JSON после команды.")
            return

    status_msg = await m.answer("⏳ Запускаю пересборку видео...")
    try:
        result = await rerender_last_render_session(m.from_user.id, overrides)
    except VideoEditingError as exc:
        await status_msg.edit_text(f"❌ Ошибка при пересборке: {exc}")
        return

    await status_msg.edit_text("✅ Новая версия готова!")
    set_last_generated_video(
        m.from_user.id,
        result.get("r2_key"),
        result.get("url"),
    )
    if result.get("url"):
        await m.answer_video(
            result["url"],
            caption="🎬 Пересобранный вариант видео",
        )
    else:
        await m.answer("Видео пересобрано, но ссылка недоступна.")


@dp.message(Command("editrender"))
async def edit_render_command(m: Message, state: FSMContext) -> None:
    await _start_render_editing_flow(m, m.from_user.id, state)


@dp.callback_query(StateFilter(UGCCreation.waiting_editing_decision), F.data == "render_edit:open")
async def render_edit_open_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await _start_render_editing_flow(c.message, c.from_user.id, state)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:templates")
async def render_edit_templates_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await c.message.answer(
        "Введи список шаблонов через запятую.\n"
        f"Доступно: {', '.join(ALLOWED_TEMPLATES)}.\n"
        "Например: mix_basic_circle,overlay\n"
        "Напиши «отмена», чтобы вернуться.",
    )
    await state.set_state(RenderEditing.waiting_templates)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:subtitles")
async def render_edit_subtitles_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await c.message.answer("Введи режим субтитров: auto или none. Напиши «отмена», чтобы вернуться.")
    await state.set_state(RenderEditing.waiting_subtitles)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:intro")
async def render_edit_intro_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await c.message.answer(
        "Отправь параметры интро:\n"
        "• off — чтобы отключить\n"
        "• или строку вида: <URL> <длительность> [шаблоны]\n"
        "Пример: https://example.com/intro.mp4 2.5 mix_basic_circle\n"
        "Напиши «отмена», чтобы вернуться.",
    )
    await state.set_state(RenderEditing.waiting_intro)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:outro")
async def render_edit_outro_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await c.message.answer(
        "Отправь параметры аутро:\n"
        "• off — чтобы отключить\n"
        "• или строку вида: <URL> <длительность> [шаблоны]\n"
        "Напиши «отмена», чтобы вернуться.",
    )
    await state.set_state(RenderEditing.waiting_outro)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:circle")
async def render_edit_circle_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await c.message.answer(
        "Введи параметры круга: <radius> <center_x> <center_y> [auto|manual]\n"
        "Значения от 0 до 1. Пример: 0.32 0.48 0.55 auto\n"
        "Напиши «отмена», чтобы вернуться.",
    )
    await state.set_state(RenderEditing.waiting_circle)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:cancel")
async def render_edit_cancel_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer("Настройки закрыты")
    await state.clear()
    await c.message.answer(
        "Настройки рендера закрыты.",
        reply_markup=_video_menu_for_user(c.from_user.id),
    )


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:rerender")
async def render_edit_rerender_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    status_msg = await c.message.answer("⏳ Пересобираю видео с новыми настройками...")
    try:
        result = await rerender_last_render_session(c.from_user.id, overrides)
    except VideoEditingError as exc:
        await status_msg.edit_text(f"❌ Ошибка при пересборке: {exc}")
        return

    set_last_generated_video(
        c.from_user.id,
        result.get("r2_key"),
        result.get("url"),
    )
    await status_msg.edit_text("✅ Готово! Отправляю видео.")
    if result.get("url"):
        await c.message.answer_video(
            result["url"],
            caption="🎬 Новая версия видео",
        )
    else:
        await c.message.answer("Видео пересобрано, но ссылка недоступна.")
    await state.clear()
    await c.message.answer(
        "Можешь продолжить монтаж или завершить.",
        reply_markup=_video_menu_for_user(c.from_user.id),
    )


@dp.message(StateFilter(RenderEditing.waiting_templates))
async def render_edit_templates_message(m: Message, state: FSMContext) -> None:
    if not m.text:
        await m.answer("Отправь текст с шаблонами или напиши «отмена».")
        return
    text = m.text.strip()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    if _is_cancel_text(text):
        await _back_to_render_menu(m, state, overrides)
        return
    templates = [item.strip() for item in re.split(r"[,\s]+", text) if item.strip()]
    if not templates:
        await m.answer("Нужно указать хотя бы один шаблон.")
        return
    invalid = [item for item in templates if item not in ALLOWED_TEMPLATES]
    if invalid:
        await m.answer(f"Некорректные шаблоны: {', '.join(invalid)}")
        return
    overrides["templates"] = templates
    await _store_overrides(state, overrides)
    await m.answer("✅ Шаблоны обновлены.")
    await _back_to_render_menu(m, state, overrides)


@dp.message(StateFilter(RenderEditing.waiting_subtitles))
async def render_edit_subtitles_message(m: Message, state: FSMContext) -> None:
    if not m.text:
        await m.answer("Отправь текст или напиши «отмена».")
        return
    text = m.text.strip().lower()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    if _is_cancel_text(text):
        await _back_to_render_menu(m, state, overrides)
        return
    if text not in {"auto", "none"}:
        await m.answer("Используй значения auto или none.")
        return
    overrides["subtitles"]["mode"] = text
    if text == "none":
        overrides["subtitles"]["transcript"] = None
        overrides["subtitles"]["file_r2_key"] = None
    await _store_overrides(state, overrides)
    await m.answer("✅ Режим субтитров обновлен.")
    await _back_to_render_menu(m, state, overrides)


@dp.message(StateFilter(RenderEditing.waiting_intro))
async def render_edit_intro_message(m: Message, state: FSMContext) -> None:
    if not m.text:
        await m.answer("Отправь текст или напиши «отмена».")
        return
    text = m.text.strip()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    if _is_cancel_text(text):
        await _back_to_render_menu(m, state, overrides)
        return
    try:
        clip_settings = _parse_clip_settings(text, overrides["templates"])
    except ValueError as exc:
        await m.answer(f"⚠️ {exc}")
        return
    overrides["intro"].update(clip_settings)
    await _store_overrides(state, overrides)
    await m.answer("✅ Настройки интро обновлены.")
    await _back_to_render_menu(m, state, overrides)


@dp.message(StateFilter(RenderEditing.waiting_outro))
async def render_edit_outro_message(m: Message, state: FSMContext) -> None:
    if not m.text:
        await m.answer("Отправь текст или напиши «отмена».")
        return
    text = m.text.strip()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    if _is_cancel_text(text):
        await _back_to_render_menu(m, state, overrides)
        return
    try:
        clip_settings = _parse_clip_settings(text, overrides["templates"])
    except ValueError as exc:
        await m.answer(f"⚠️ {exc}")
        return
    overrides["outro"].update(clip_settings)
    await _store_overrides(state, overrides)
    await m.answer("✅ Настройки аутро обновлены.")
    await _back_to_render_menu(m, state, overrides)


@dp.message(StateFilter(RenderEditing.waiting_circle))
async def render_edit_circle_message(m: Message, state: FSMContext) -> None:
    if not m.text:
        await m.answer("Отправь текст или напиши «отмена».")
        return
    text = m.text.strip()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    if _is_cancel_text(text):
        await _back_to_render_menu(m, state, overrides)
        return
    try:
        updated_circle = _parse_circle_settings(text, overrides["circle"])
    except ValueError as exc:
        await m.answer(f"⚠️ {exc}")
        return
    overrides["circle"] = updated_circle
    await _store_overrides(state, overrides)
    await m.answer("✅ Настройки круга обновлены.")
    await _back_to_render_menu(m, state, overrides)


@dp.message(Command("resume"))
async def resume_editing_command(m: Message, state: FSMContext):
    """Системная команда для возобновления монтажа после перезапуска бота"""
    # Проверяем, есть ли сохраненное видео
    video_data = get_original_video(m.from_user.id)
    
    if not video_data or not video_data.get('r2_key'):
        await m.answer(
            "❌ Нет незавершенного монтажа.\n\n"
            "Создайте новое видео:",
            reply_markup=main_menu()
        )
        return
    
    # Проверяем, было ли уже отредактированное видео
    edited_video = get_last_generated_video(m.from_user.id)
    
    if edited_video and edited_video.get('r2_key'):
        # Уже есть отредактированная версия
        await m.answer(
            "✅ Найдено отредактированное видео!\n\n"
            "Хочешь смонтировать еще раз или завершить?",
            reply_markup=_video_menu_for_user(m.from_user.id)
        )
    else:
        # Есть только исходное видео
        await m.answer(
            "✅ Найдено исходное видео!\n\n"
            "Хочешь смонтировать его?",
            reply_markup=_video_menu_for_user(m.from_user.id)
        )
    
    # Устанавливаем состояние
    await state.set_state(UGCCreation.waiting_editing_decision)
    logger.info(f"User {m.from_user.id} resumed editing session via /resume command")


@dp.message(Command("overlay"))
async def regenerate_overlay_command(m: Message, state: FSMContext):
    """Команда для перегенерации оверлея с новыми параметрами"""
    # Проверяем, есть ли сохраненное видео
    video_data = get_original_video(m.from_user.id)
    
    if not video_data or not video_data.get('r2_key'):
        await m.answer(
            "❌ Нет сохраненного видео для перегенерации оверлея.\n\n"
            "Создайте новое видео:",
            reply_markup=main_menu()
        )
        return
    
    # Очищаем кеш оверлеев, чтобы они сгенерировались заново
    set_cached_overlay_urls(m.from_user.id, {}, {})
    logger.info(f"User {m.from_user.id} cleared overlay cache via /overlay command")
    
    # Предлагаем начать монтаж с новым оверлеем
    await m.answer(
        "✅ Кеш оверлеев очищен!\n\n"
        "Теперь при монтаже будет создан новый оверлей.\n"
        "Хочешь начать монтаж?",
        reply_markup=_video_menu_for_user(m.from_user.id)
    )
    
    # Устанавливаем состояние
    await state.set_state(UGCCreation.waiting_editing_decision)
    logger.info(f"User {m.from_user.id} ready to regenerate overlay")


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
        
        # Отправляем статусное сообщение с предупреждением о времени
        status_msg = await c.message.answer(
            "⏳ Начинаю монтаж видео...\n\n"
            "⚠️ Это займет примерно 5 минут"
        )
        
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
                        reply_markup=_video_menu_for_user(c.from_user.id)
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
                reply_markup=_video_menu_for_user(c.from_user.id)
            )
            
        except VideoEditingError as e:
            logger.error(f"Video editing error for user {c.from_user.id}: {e}")
            await status_msg.delete()
            
            # ✨ НЕ ОЧИЩАЕМ СОСТОЯНИЕ - даем повторить попытку
            await c.message.answer(
                "❌ Произошла ошибка при монтаже видео.\n\n"
                "Попробуйте еще раз или завершите:",
                reply_markup=_video_menu_for_user(c.from_user.id)
            )
            # Остаемся в состоянии waiting_editing_decision
            
        except Exception as e:
            logger.error(f"Unexpected error in video editing for user {c.from_user.id}: {e}", exc_info=True)
            await status_msg.delete()
            
            # ✨ НЕ ОЧИЩАЕМ СОСТОЯНИЕ - даем повторить попытку
            await c.message.answer(
                "❌ Произошла неожиданная ошибка.\n\n"
                "Попробуйте еще раз или завершите:",
                reply_markup=_video_menu_for_user(c.from_user.id)
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
    
    # Проверяем, был ли монтаж (до очистки!)
    edited_video = get_last_generated_video(c.from_user.id)
    
    # Очищаем все данные о видео
    clear_all_video_data(c.from_user.id)
    
    # Очищаем состояние
    await state.clear()
    
    # Возвращаемся в главное меню одним сообщением
    if edited_video and edited_video.get('r2_key'):
        # Был монтаж
        await c.message.edit_text(
            "✅ Отлично! Видео с монтажом готово.\n\n"
            "🎬 Хочешь создать еще одну UGC рекламу?",
            reply_markup=main_menu()
        )
    else:
        # Монтажа не было
        await c.message.edit_text(
            "✅ Отлично! Видео готово.\n\n"
            "🎬 Хочешь создать еще одну UGC рекламу?",
            reply_markup=main_menu()
        )
