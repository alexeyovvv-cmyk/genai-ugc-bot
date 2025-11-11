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
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional, Sequence

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
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
from tg_bot.services.r2_service import upload_file, delete_file
from tg_bot.dispatcher import dp
from tg_bot.utils.logger import setup_logger
from video_editing.common.media.meta import run_ffprobe_meta

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
    intro_desc = "вкл (файл)" if intro.get("r2_key") else ("вкл" if intro.get("enabled") else "выкл")
    outro_desc = "вкл (файл)" if outro.get("r2_key") else ("вкл" if outro.get("enabled") else "выкл")
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


def _build_templates_keyboard(selected: Sequence[str]) -> InlineKeyboardMarkup:
    rows = []
    for template in ALLOWED_TEMPLATES:
        active = template in selected
        icon = "✅" if active else "⬜️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {template}",
                    callback_data=f"render_edit:tpl_toggle:{template}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="render_edit:tpl_done"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="render_edit:tpl_cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_subtitles_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    auto_active = current_mode == "auto"
    none_active = current_mode == "none"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✅ Auto" if auto_active else "Auto"),
                    callback_data="render_edit:subs_set:auto",
                ),
                InlineKeyboardButton(
                    text=("✅ None" if none_active else "None"),
                    callback_data="render_edit:subs_set:none",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="render_edit:subs_back")],
        ]
    )


def _clip_has_asset(settings: dict) -> bool:
    return bool(settings.get("r2_key") or settings.get("url"))


def _build_clip_menu(kind: str, has_asset: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📤 Загрузить файл", callback_data=f"render_edit:{kind}_upload")],
    ]
    if has_asset:
        rows.append([InlineKeyboardButton(text="🚫 Отключить", callback_data=f"render_edit:{kind}_disable")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"render_edit:{kind}_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_render_settings_message(target_message: Message, overrides: dict) -> None:
    text = _format_render_summary(overrides)
    await target_message.answer(text, reply_markup=render_settings_menu(), parse_mode="HTML")


def _video_menu_for_user(user_id: int):
    has_render = get_render_session_summary(user_id) is not None
    return video_editing_menu(has_render)


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


async def _delete_message_safe(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


def _cleanup_clip_asset(clip_settings: dict) -> None:
    old_key = clip_settings.get("r2_key")
    if old_key:
        try:
            delete_file(old_key)
        except Exception:
            pass
    clip_settings["r2_key"] = None
    clip_settings["url"] = None


def _clip_display_name(kind: str) -> str:
    return "интро" if kind == "intro" else "аутро"


def _extract_video_file_info(message: Message) -> Optional[dict]:
    if message.video:
        return {
            "file_id": message.video.file_id,
            "file_name": message.video.file_name or "video.mp4",
            "duration": message.video.duration,
        }
    document = message.document
    if document and document.mime_type and document.mime_type.lower().startswith("video"):
        return {
            "file_id": document.file_id,
            "file_name": document.file_name or "video.mp4",
            "duration": getattr(document, "duration", None),
        }
    return None


async def _process_clip_upload_message(message: Message, state: FSMContext, clip_key: str) -> None:
    file_info = _extract_video_file_info(message)
    if not file_info:
        await message.answer("Отправь видеофайл (MP4/MOV) или напиши «отмена».")
        return False

    from tg_bot.main import bot  # импорт внутри функции, чтобы избежать циклических зависимостей

    telegram_file = await bot.get_file(file_info["file_id"])
    suffix = Path(telegram_file.file_path).suffix or Path(file_info["file_name"]).suffix or ".mp4"
    timestamp = int(time.time())

    with tempfile.TemporaryDirectory(prefix=f"{clip_key}_upload_") as tmpdir:
        tmp_path = Path(tmpdir) / f"{clip_key}_{timestamp}{suffix}"
        await bot.download_file(telegram_file.file_path, tmp_path)
        duration = file_info.get("duration")
        if not duration:
            try:
                meta = run_ffprobe_meta(tmp_path, error_cls=RuntimeError)
                duration = meta.duration
            except Exception:
                duration = None
        r2_key = f"users/{message.from_user.id}/{clip_key}s/{clip_key}_{timestamp}{suffix}"
        if not upload_file(str(tmp_path), r2_key):
            await message.answer("❌ Не удалось сохранить файл. Попробуй еще раз.")
            return False

    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    clip_settings = overrides[clip_key]
    _cleanup_clip_asset(clip_settings)
    clip_settings["enabled"] = True
    clip_settings["r2_key"] = r2_key
    clip_settings["url"] = None
    clip_settings["length"] = round(float(duration or DEFAULT_INTRO_LENGTH), 3)
    clip_settings.setdefault("templates", overrides["templates"])

    await _store_overrides(state, overrides)
    await message.answer(f"✅ { _clip_display_name(clip_key).capitalize() } обновлено.")
    await state.set_state(RenderEditing.choosing_action)
    await _send_render_settings_message(message, overrides)
    return True


async def _open_clip_menu(callback: CallbackQuery, state: FSMContext, clip_key: str) -> None:
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    keyboard = _build_clip_menu(clip_key, _clip_has_asset(overrides[clip_key]))
    message = await callback.message.answer(
        f"Настройка { _clip_display_name(clip_key) }:",
        reply_markup=keyboard,
    )
    await state.update_data({f"{clip_key}_menu_message_id": message.message_id})


async def _close_clip_menu(message: Message, state: FSMContext, clip_key: str) -> None:
    await _delete_message_safe(message)
    await state.update_data({f"{clip_key}_menu_message_id": None})


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
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    keyboard = _build_templates_keyboard(overrides["templates"])
    message = await c.message.answer(
        "Выбери шаблоны, которые нужно рендерить:",
        reply_markup=keyboard,
    )
    await state.set_state(RenderEditing.editing_templates)
    await state.update_data(templates_menu_message_id=message.message_id)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:subtitles")
async def render_edit_subtitles_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    keyboard = _build_subtitles_keyboard(overrides["subtitles"].get("mode", "auto"))
    message = await c.message.answer(
        "Выбери режим субтитров:",
        reply_markup=keyboard,
    )
    await state.set_state(RenderEditing.editing_subtitles)
    await state.update_data(subtitles_menu_message_id=message.message_id)


@dp.callback_query(StateFilter(RenderEditing.editing_templates), F.data.startswith("render_edit:tpl_toggle:"))
async def render_edit_templates_toggle(c: CallbackQuery, state: FSMContext) -> None:
    template = c.data.split(":")[-1]
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    selected = overrides["templates"]
    if template in selected:
        if len(selected) == 1:
            await c.answer("Нельзя убрать последний шаблон", show_alert=True)
            return
        selected = [item for item in selected if item != template]
    else:
        selected = selected + [template]
    overrides["templates"] = selected
    await _store_overrides(state, overrides)
    await c.message.edit_reply_markup(reply_markup=_build_templates_keyboard(selected))
    await c.answer("Обновлено")


@dp.callback_query(StateFilter(RenderEditing.editing_templates), F.data.in_(["render_edit:tpl_done", "render_edit:tpl_cancel"]))
async def render_edit_templates_finish(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    await _back_to_render_menu(c.message, state, overrides)
    await _delete_message_safe(c.message)
    await state.update_data(templates_menu_message_id=None)


@dp.callback_query(StateFilter(RenderEditing.editing_subtitles), F.data.startswith("render_edit:subs_set:"))
async def render_edit_subtitles_set(c: CallbackQuery, state: FSMContext) -> None:
    mode = c.data.split(":")[-1]
    await c.answer()
    if mode not in {"auto", "none"}:
        return
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    overrides["subtitles"]["mode"] = mode
    if mode == "none":
        overrides["subtitles"]["transcript"] = None
        overrides["subtitles"]["file_r2_key"] = None
    await _store_overrides(state, overrides)
    await _back_to_render_menu(c.message, state, overrides)
    await _delete_message_safe(c.message)
    await state.update_data(subtitles_menu_message_id=None)


@dp.callback_query(StateFilter(RenderEditing.editing_subtitles), F.data == "render_edit:subs_back")
async def render_edit_subtitles_back(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    await _back_to_render_menu(c.message, state, overrides)
    await _delete_message_safe(c.message)
    await state.update_data(subtitles_menu_message_id=None)


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:intro")
async def render_edit_intro_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await _open_clip_menu(c, state, "intro")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:outro")
async def render_edit_outro_callback(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await _open_clip_menu(c, state, "outro")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:intro_back")
async def render_edit_intro_back(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    await _back_to_render_menu(c.message, state, overrides)
    await _close_clip_menu(c.message, state, "intro")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:outro_back")
async def render_edit_outro_back(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    await _back_to_render_menu(c.message, state, overrides)
    await _close_clip_menu(c.message, state, "outro")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:intro_disable")
async def render_edit_intro_disable(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    clip = overrides["intro"]
    _cleanup_clip_asset(clip)
    clip["enabled"] = False
    await _store_overrides(state, overrides)
    await _back_to_render_menu(c.message, state, overrides)
    await _close_clip_menu(c.message, state, "intro")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:outro_disable")
async def render_edit_outro_disable(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    data = await state.get_data()
    overrides = _get_overrides_from_state(data)
    clip = overrides["outro"]
    _cleanup_clip_asset(clip)
    clip["enabled"] = False
    await _store_overrides(state, overrides)
    await _back_to_render_menu(c.message, state, overrides)
    await _close_clip_menu(c.message, state, "outro")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:intro_upload")
async def render_edit_intro_upload(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await _close_clip_menu(c.message, state, "intro")
    await state.set_state(RenderEditing.waiting_intro_upload)
    await state.update_data(clip_upload_kind="intro")
    await c.message.answer("Отправь видеофайл для интро (или напиши «отмена»).")


@dp.callback_query(StateFilter(RenderEditing.choosing_action), F.data == "render_edit:outro_upload")
async def render_edit_outro_upload(c: CallbackQuery, state: FSMContext) -> None:
    await c.answer()
    await _close_clip_menu(c.message, state, "outro")
    await state.set_state(RenderEditing.waiting_outro_upload)
    await state.update_data(clip_upload_kind="outro")
    await c.message.answer("Отправь видеофайл для аутро (или напиши «отмена»).")


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


@dp.message(StateFilter(RenderEditing.waiting_intro_upload))
async def render_edit_intro_upload_message(m: Message, state: FSMContext) -> None:
    if m.text and _is_cancel_text(m.text):
        data = await state.get_data()
        overrides = _get_overrides_from_state(data)
        await state.set_state(RenderEditing.choosing_action)
        await m.answer("Загрузка интро отменена.")
        await _send_render_settings_message(m, overrides)
        await state.update_data(clip_upload_kind=None)
        return
    success = await _process_clip_upload_message(m, state, "intro")
    if success:
        await state.update_data(clip_upload_kind=None)


@dp.message(StateFilter(RenderEditing.waiting_outro_upload))
async def render_edit_outro_upload_message(m: Message, state: FSMContext) -> None:
    if m.text and _is_cancel_text(m.text):
        data = await state.get_data()
        overrides = _get_overrides_from_state(data)
        await state.set_state(RenderEditing.choosing_action)
        await m.answer("Загрузка аутро отменена.")
        await _send_render_settings_message(m, overrides)
        await state.update_data(clip_upload_kind=None)
        return
    success = await _process_clip_upload_message(m, state, "outro")
    if success:
        await state.update_data(clip_upload_kind=None)


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
