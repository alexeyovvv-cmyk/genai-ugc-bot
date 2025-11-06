from __future__ import annotations

import copy
import json
from typing import Any, Dict, Iterable, List, Optional, Type


def load_blocks_config(
    path: Optional[str],
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise error_cls(f"Не удалось прочитать blocks-config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise error_cls("Файл blocks-config должен содержать объект с ключами сценариев.")
    return data


def _track_end(clips: List[Dict[str, Any]]) -> float:
    end = 0.0
    for clip in clips:
        try:
            start = float(clip.get("start", 0.0) or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        length = clip.get("length")
        if isinstance(length, (int, float)):
            end = max(end, start + float(length))
        elif clip.get("auto_length"):
            end = max(end, start)
    return end


def _shift_starts(entries: Iterable[Dict[str, Any]], shift: float) -> None:
    if shift <= 0:
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            start = float(entry.get("start", 0.0) or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        entry["start"] = round(start + shift, 3)


def apply_blocks(
    spec: Dict[str, Any],
    blocks_cfg: Dict[str, Any],
    base_duration: Optional[float],
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> None:
    if not blocks_cfg:
        return

    clips = spec.setdefault("clips", [])
    overlays = spec.setdefault("overlays", [])

    intro_total = 0.0
    prepend_clips = blocks_cfg.get("prepend_clips", [])
    if prepend_clips:
        if not isinstance(prepend_clips, list):
            raise error_cls("prepend_clips в blocks-config должен быть массивом.")
        intro_clips: List[Dict[str, Any]] = []
        offset = 0.0
        for entry in prepend_clips:
            if not isinstance(entry, dict):
                raise error_cls("Каждый prepend_clips должен быть объектом.")
            clip = copy.deepcopy(entry)
            if "length" not in clip:
                raise error_cls("Клип в prepend_clips обязан содержать поле length.")
            try:
                length = float(clip["length"])
            except (TypeError, ValueError) as exc:
                raise error_cls("Поле length в prepend_clips должно быть числом.") from exc
            clip.setdefault("start", round(offset, 3))
            intro_clips.append(clip)
            offset += length

        if intro_clips:
            _shift_starts(clips, offset)
            _shift_starts(overlays, offset)
            _shift_starts(spec.get("subtitles", []), offset)
            clips[:] = intro_clips + clips
            intro_total = offset

    append_clips = blocks_cfg.get("append_clips", [])
    if append_clips:
        if not isinstance(append_clips, list):
            raise error_cls("append_clips в blocks-config должен быть массивом.")
        timeline_base = _track_end(clips)
        if base_duration and base_duration > 0:
            base_length = base_duration
        else:
            base_length = max(timeline_base - intro_total, 0.0)
        append_offset = 0.0
        for entry in append_clips:
            if not isinstance(entry, dict):
                raise error_cls("Каждый append_clips должен быть объектом.")
            clip = copy.deepcopy(entry)
            if clip.get("start") is None:
                clip["start"] = round(intro_total + base_length + append_offset, 3)
            append_offset += float(clip.get("length", 0.0) or 0.0)
            clips.append(clip)

    append_overlays = blocks_cfg.get("append_overlays", [])
    if append_overlays:
        if not isinstance(append_overlays, list):
            raise error_cls("append_overlays в blocks-config должен быть массивом.")
        for entry in append_overlays:
            if not isinstance(entry, dict):
                raise error_cls("Каждый append_overlays должен быть объектом.")
            overlay = copy.deepcopy(entry)
            if overlay.get("start") is None:
                overlay["start"] = round(_track_end(overlays), 3)
            overlays.append(overlay)
