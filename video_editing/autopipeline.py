#!/usr/bin/env python3
"""
End-to-end automation around the talking-head pipeline.

Steps performed:
    1. Download фон и говорящую голову (для анализа аспектов).
    2. Генерирует прозрачный оверлей (rect и, при необходимости, circle) через prepare_overlay.
    3. Настраивает выбранные JSON-шаблоны: подставляет свежие ссылки, подбирает режим fit
       (cover/contain) под формат фона и складывает результирующие спецификации в build/auto_*/.
    4. Запускает render через assemble.py и возвращает ссылки на итоговые mp4.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import copy
import re

import assemble
import prepare_overlay

# Import new utility modules
from common.media.meta import MediaMeta, run_ffprobe_meta as run_ffprobe_meta_new, decide_fit as decide_fit_new, sniff_remote_media_type
from render.templates.spec_editor import load_spec as load_spec_new, save_spec as save_spec_new, ensure_background as ensure_background_new, get_node as get_node_new, update_nodes as update_nodes_new
from render.timeline.blocks import load_blocks_config as load_blocks_config_new, apply_blocks as apply_blocks_new
from render.subtitle import subtitle_tools

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

TARGET_ASPECT = 9 / 16
DEFAULT_FIT_TOLERANCE = 0.02
BUILD_ROOT = Path("build")


class PipelineError(RuntimeError):
    """Raised for any automation failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate the talking-head workflow end-to-end.")
    parser.add_argument("--background-url", required=True, help="Ссылка на фон (скринкаст).")
    parser.add_argument("--head-url", required=True, help="Ссылка на исходник говорящей головы.")
    parser.add_argument(
        "--templates",
        default="overlay,circle,basic,mix_basic_overlay,mix_basic_circle",
        help="Список шаблонов через запятую (overlay|circle|basic|mix_basic_overlay|mix_basic_circle).",
    )
    parser.add_argument(
        "--output-dir",
        help="Каталог, куда положить сгенерированные спецификации.",
    )
    parser.add_argument(
        "--fit-tolerance",
        type=float,
        default=DEFAULT_FIT_TOLERANCE,
        help="Допустимое отклонение аспекта от 9:16 прежде чем ставить fit=contain.",
    )
    parser.add_argument(
        "--overlay-engine",
        choices=["mediapipe", "rembg"],
        default=os.getenv("OVERLAY_ENGINE", "rembg"),
        help="Движок вырезки для prepare_overlay (по умолчанию rembg).",
    )
    parser.add_argument(
        "--overlay-container",
        choices=["mov", "webm"],
        default=os.getenv("OVERLAY_CONTAINER", "mov"),
        help="Контейнер для прозрачного оверлея (по умолчанию mov).",
    )
    parser.add_argument(
        "--rembg-model",
        default=os.getenv("REMBG_MODEL", "u2netp"),
        help="Модель rembg (по умолчанию u2netp).",
    )
    parser.add_argument(
        "--rembg-alpha-matting",
        action="store_true",
        help="Включить alpha-matting для rembg.",
    )
    parser.add_argument(
        "--circle-radius",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_RADIUS", "0.35")),
        help="Радиус круга (0-1) для circle-оверлея.",
    )
    parser.add_argument(
        "--circle-center-x",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_CENTER_X", "0.5")),
        help="Горизонтальный центр круга (0-1).",
    )
    parser.add_argument(
        "--circle-center-y",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_CENTER_Y", "0.5")),
        help="Вертикальный центр круга (0-1).",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Только сгенерировать спецификации, без запуска рендера.",
    )
    parser.add_argument(
        "--background-color",
        default="#000000",
        help="Цвет подложки при fit=contain (default: чёрный).",
    )
    parser.add_argument(
        "--subtitles-enabled",
        choices=["auto", "none", "manual"],
        default="auto",
        help="Настройка субтитров: auto (по умолчанию), none (отключить), manual (использовать только готовый JSON).",
    )
    parser.add_argument(
        "--subtitles",
        help="Путь к JSON с субтитрами (список объектов start/length/text или файл с ключом subtitles).",
    )
    parser.add_argument(
        "--transcript",
        help="Готовый текст для авторазметки субтитров (будет выровнен по речи говорящей головы).",
    )
    parser.add_argument(
        "--transcript-file",
        help="Файл с текстом субтитров для авторазметки (альтернатива --transcript).",
    )
    parser.add_argument(
        "--blocks-config",
        default="render/timeline/config/blocks.json",
        help="JSON с описанием дополнительных блоков (append_clips/append_overlays) по сценариям.",
    )
    parser.add_argument(
        "--intro-url",
        help="URL интро-клипа. Если указан, будет добавлен в начало выбранных сценариев.",
    )
    parser.add_argument(
        "--intro-length",
        type=float,
        default=2.5,
        help="Длительность интро (секунды, default: 2.5).",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        help="User ID for caching overlay results.",
    )
    parser.add_argument(
        "--intro-templates",
        help="Список шаблонов для интро (через запятую). По умолчанию — все выбранные сценарии.",
    )
    parser.add_argument(
        "--outro-url",
        help="URL аутро-клипа. Если указан, будет добавлен в конец выбранных сценариев.",
    )
    parser.add_argument(
        "--outro-length",
        type=float,
        default=2.5,
        help="Длительность аутро (секунды, default: 2.5).",
    )
    parser.add_argument(
        "--outro-templates",
        help="Список шаблонов для аутро (через запятую). По умолчанию — все выбранные сценарии.",
    )
    parser.add_argument(
        "--background-video-length",
        choices=["auto", "fixed"],
        default="auto",
        help="Поведение для видеофона: auto — подогнать длительность под голову, fixed — оставить как в исходнике.",
    )
    parser.add_argument(
        "--subtitle-theme",
        choices=["light", "yellow_on_black"],
        default="light",
        help="Цветовая схема субтитров: light (по умолчанию) или yellow_on_black.",
    )
    parser.add_argument(
        "--no-circle-auto-center",
        action="store_false",
        dest="circle_auto_center",
        help="Отключить авто-центровку круга и использовать заданные вручную координаты.",
    )
    parser.set_defaults(circle_auto_center=True)
    return parser.parse_args()


def parse_template_list(raw: Optional[str], default: Sequence[str]) -> List[str]:
    if raw is None:
        return list(default)
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or list(default)


TemplateName = str


TEMPLATE_REGISTRY: Dict[TemplateName, Dict[str, object]] = {
    "overlay": {
        "file": "render/templates/presets/talking_head_overlay.json",
        "background_nodes": [("clips", 0)],
        "overlay_nodes": {"rect": [("overlays", 0)]},
    },
    "circle": {
        "file": "render/templates/presets/talking_head_circle.json",
        "background_nodes": [("clips", 0)],
        "overlay_nodes": {"circle": [("overlays", 0)]},
    },
    "basic": {
        "file": "render/templates/presets/talking_head_basic.json",
        "head_nodes": [("clips", 0), ("clips", 1)],
        "background_nodes": [("overlays", 0)],
    },
    "mix_basic_overlay": {
        "file": "render/templates/presets/talking_head_mix_basic_overlay.json",
        "head_nodes": [("clips", 0), ("clips", 1)],
        "background_nodes": [("overlays", 1)],
        "overlay_nodes": {"rect": [("overlays", 0)]},
    },
    "mix_basic_circle": {
        "file": "render/templates/presets/talking_head_mix_basic_circle.json",
        "head_nodes": [("clips", 0), ("clips", 1)],
        "background_nodes": [("overlays", 1)],
        "overlay_nodes": {"circle": [("overlays", 0)]},
    },
}


def validate_templates(names: Iterable[TemplateName]) -> List[TemplateName]:
    valid: List[TemplateName] = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        if name not in TEMPLATE_REGISTRY:
            raise PipelineError(f"Неизвестный шаблон: {name}")
        valid.append(name)
    if not valid:
        raise PipelineError("Список шаблонов пуст.")
    return valid


def run_ffprobe_meta(video_path: Path) -> Tuple[int, int, float]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except FileNotFoundError as exc:
        raise PipelineError("Нужен ffprobe, но бинарь не найден в PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise PipelineError(f"ffprobe не смог прочитать {video_path}: {exc.stderr.strip()}") from exc

    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, ValueError, IndexError) as exc:
        raise PipelineError(f"Не удалось распарсить метаданные ffprobe: {result.stdout}") from exc

    duration = assemble._probe_duration(str(video_path))
    return width, height, duration


def decide_fit(width: int, height: int, tolerance: float) -> str:
    if width <= 0 or height <= 0:
        return "cover"
    aspect = width / height
    if abs(aspect - TARGET_ASPECT) <= tolerance:
        return "cover"
    return "contain"


def ensure_background(spec: Dict[str, object], color: str) -> None:
    spec["background"] = color


def load_subtitles(path: str) -> List[Dict[str, object]]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"Не удалось прочитать субтитры из {path}: {exc}") from exc

    if isinstance(data, dict):
        if "subtitles" in data:
            data = data["subtitles"]
        elif "cues" in data:
            data = data["cues"]

    if not isinstance(data, list):
        raise PipelineError("Файл субтитров должен содержать массив объектов.")

    subtitles: List[Dict[str, object]] = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise PipelineError(f"Субтитр #{index} должен быть объектом.")

        text = str(entry.get("text", "")).strip()
        if not text:
            continue

        try:
            start = float(entry.get("start", 0.0))
        except (TypeError, ValueError) as exc:
            raise PipelineError(f"Субтитр #{index} имеет некорректное поле start.") from exc

        if "length" in entry:
            try:
                length = float(entry["length"])
            except (TypeError, ValueError) as exc:
                raise PipelineError(f"Субтитр #{index} имеет некорректное поле length.") from exc
        elif "end" in entry:
            try:
                end = float(entry["end"])
            except (TypeError, ValueError) as exc:
                raise PipelineError(f"Субтитр #{index} имеет некорректное поле end.") from exc
            length = max(end - start, 0.0)
        else:
            raise PipelineError(f"Субтитр #{index} должен содержать length или end.")

        if length <= 0:
            continue

        subtitle: Dict[str, object] = {
            "text": text,
            "start": start,
            "length": length,
        }

        if entry.get("position"):
            subtitle["position"] = entry["position"]
        if entry.get("offset"):
            subtitle["offset"] = entry["offset"]
        if entry.get("width"):
            subtitle["width"] = entry["width"]

        subtitles.append(subtitle)

    return subtitles


def read_transcript(args: argparse.Namespace) -> Optional[str]:
    if args.transcript_file:
        try:
            return Path(args.transcript_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise PipelineError(f"Не удалось прочитать файл транскрипта {args.transcript_file}: {exc}") from exc
    if args.transcript:
        return args.transcript
    return None


def detect_speech_segments(
    media_path: Path,
    duration: float,
    silence_db: float = -35.0,
    min_silence_duration: float = 0.35,
    min_segment_duration: float = 0.3,
) -> List[Tuple[float, float]]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(media_path),
        "-af",
        f"silencedetect=noise={silence_db}dB:d={min_silence_duration}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise PipelineError(f"ffmpeg silencedetect failed: {result.stderr.strip()}")

    current_start = 0.0
    speech_segments: List[Tuple[float, float]] = []

    for line in result.stderr.splitlines():
        line = line.strip()
        if "silence_start" in line:
            try:
                silence_start = float(line.split("silence_start:")[1].split()[0])
            except (IndexError, ValueError):
                continue
            segment_duration = silence_start - current_start
            if segment_duration >= min_segment_duration:
                speech_segments.append((current_start, segment_duration))
            current_start = silence_start
        elif "silence_end" in line:
            try:
                silence_end = float(line.split("silence_end:")[1].split()[0])
            except (IndexError, ValueError):
                continue
            current_start = silence_end

    if duration > current_start:
        tail_duration = duration - current_start
        if tail_duration >= min_segment_duration:
            speech_segments.append((current_start, tail_duration))

    if not speech_segments and duration > 0:
        speech_segments = [(0.0, duration)]

    return speech_segments


def sentence_tokenize(text: str) -> List[str]:
    stripped = text.strip()
    if not stripped:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()]
    if parts:
        return parts
    words = stripped.split()
    chunk_size = 10
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


def align_transcript_to_segments(
    transcript: str,
    segments: List[Tuple[float, float]],
    total_duration: float,
) -> List[Dict[str, object]]:
    sentences = sentence_tokenize(transcript)
    if not sentences:
        return []

    if not segments:
        segments = [(0.0, total_duration)]

    total_segments_duration = sum(duration for _, duration in segments)
    if total_segments_duration <= 0:
        total_segments_duration = total_duration or 1.0

    allocations: List[List[str]] = []
    sentence_index = 0
    cumulative = 0.0
    num_sentences = len(sentences)

    for seg_index, (_, duration) in enumerate(segments):
        if seg_index == len(segments) - 1:
            next_index = num_sentences
        else:
            portion = duration / total_segments_duration
            cumulative += portion * num_sentences
            next_index = max(sentence_index + 1, int(round(cumulative)))
            next_index = min(next_index, num_sentences)
        allocations.append(sentences[sentence_index:next_index])
        sentence_index = next_index

    subtitles: List[Dict[str, object]] = []
    for (seg_start, seg_duration), texts in zip(segments, allocations):
        if not texts:
            continue
        text = " ".join(texts).strip()
        if not text:
            continue
        length = max(seg_duration - min(0.15, seg_duration * 0.1), 0.4)
        length = min(length, max(seg_duration - 0.05, 0.2))
        start = max(seg_start + 0.05, 0.0)
        subtitles.append(
            {
                "start": round(start, 3),
                "length": round(length, 3),
                "text": text,
            }
        )

    return subtitles


def load_blocks_config(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"Не удалось прочитать blocks-config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PipelineError("Файл blocks-config должен содержать объект с ключами сценариев.")
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


def apply_blocks(spec: Dict[str, Any], blocks_cfg: Dict[str, Any], base_duration: Optional[float]) -> None:
    if not blocks_cfg:
        return

    clips = spec.setdefault("clips", [])
    overlays = spec.setdefault("overlays", [])

    intro_total = 0.0
    prepend_clips = blocks_cfg.get("prepend_clips", [])
    if prepend_clips:
        if not isinstance(prepend_clips, list):
            raise PipelineError("prepend_clips в blocks-config должен быть массивом.")
        intro_clips: List[Dict[str, Any]] = []
        offset = 0.0
        for entry in prepend_clips:
            if not isinstance(entry, dict):
                raise PipelineError("Каждый prepend_clips должен быть объектом.")
            clip = copy.deepcopy(entry)
            if "length" not in clip:
                raise PipelineError("Клип в prepend_clips обязан содержать поле length.")
            try:
                length = float(clip["length"])
            except (TypeError, ValueError) as exc:
                raise PipelineError("Поле length в prepend_clips должно быть числом.") from exc
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
            raise PipelineError("append_clips в blocks-config должен быть массивом.")
        timeline_base = _track_end(clips)
        if base_duration and base_duration > 0:
            base_length = base_duration
        else:
            base_length = max(timeline_base - intro_total, 0.0)
        append_offset = 0.0
        for entry in append_clips:
            if not isinstance(entry, dict):
                raise PipelineError("Каждый append_clips должен быть объектом.")
            clip = copy.deepcopy(entry)
            if clip.get("start") is None:
                clip["start"] = round(intro_total + base_length + append_offset, 3)
            append_offset += float(clip.get("length", 0.0) or 0.0)
            clips.append(clip)

    append_overlays = blocks_cfg.get("append_overlays", [])
    if append_overlays:
        if not isinstance(append_overlays, list):
            raise PipelineError("append_overlays в blocks-config должен быть массивом.")
        for entry in append_overlays:
            if not isinstance(entry, dict):
                raise PipelineError("Каждый append_overlays должен быть объектом.")
            overlay = copy.deepcopy(entry)
            if overlay.get("start") is None:
                overlay["start"] = round(_track_end(overlays), 3)
            overlays.append(overlay)


def get_node(spec: Dict[str, object], path: Sequence[object]) -> Dict[str, object]:
    node: object = spec
    for key in path:
        if isinstance(key, int):
            node = node[key]
        else:
            node = node[key]  # type: ignore[index]
    if not isinstance(node, dict):
        raise PipelineError(f"Ожидался объект dict по пути {path}, но получен {type(node).__name__}")
    return node


def update_nodes(
    spec: Dict[str, object],
    paths: Iterable[Sequence[object]],
    url: str,
    fit_mode: Optional[str] = None,
) -> None:
    for path in paths:
        clip = get_node(spec, path)
        clip["src"] = url
        if fit_mode:
            clip["fit"] = fit_mode


def generate_overlay_urls_modal(
    modal_endpoint: str,
    head_url: str,
    shapes: Iterable[str],
    *,
    container: str,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
) -> Dict[str, str]:
    """
    Generate overlay URLs using Modal GPU service.
    
    Args:
        modal_endpoint: Modal service endpoint URL
        head_url: URL of head video
        shapes: List of shapes to generate (e.g., ["circle"])
        container: "mov" or "webm"
        engine: "mediapipe" or "rembg"
        rembg_model: rembg model name
        rembg_alpha_matting: enable alpha matting for rembg
        circle_radius: circle mask radius
        circle_center_x: circle center X
        circle_center_y: circle center Y
        
    Returns:
        Dict mapping shape to overlay URL
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "tg_bot"))
    
    from services.modal_client import ModalOverlayClient
    
    client = ModalOverlayClient(
        base_url=modal_endpoint,
        poll_interval=5,
        timeout=600,
    )
    
    urls: Dict[str, str] = {}
    shapes_set = set(shapes)
    
    if not shapes_set:
        return urls
    
    overlay_start = time.time()
    
    for shape in shapes_set:
        logger.info(f"[AUTOPIPELINE] ▶️ Submitting {shape} overlay to Modal GPU")
        
        try:
            overlay_url = client.process_overlay_async(
                video_url=head_url,
                container=container,
                engine=engine,
                rembg_model=rembg_model,
                rembg_alpha_matting=rembg_alpha_matting,
                shape=shape,
                circle_radius=circle_radius,
                circle_center_x=circle_center_x,
                circle_center_y=circle_center_y,
                # Additional prepare_overlay parameters
                threshold=0.6,
                feather=7,
                rembg_fg_threshold=240,
                rembg_bg_threshold=10,
                rembg_erode_size=10,
                rembg_base_size=1000,
            )
            
            urls[shape] = overlay_url
            logger.info(f"[AUTOPIPELINE] ✅ {shape} overlay ready")
            
        except Exception as exc:
            logger.error(f"[AUTOPIPELINE] ❌ Modal GPU failed for {shape}: {exc}")
            raise PipelineError(f"Modal GPU overlay generation failed: {exc}") from exc
    
    overlay_duration = time.time() - overlay_start
    logger.info(f"[AUTOPIPELINE] ⏱️ Overlays generated via Modal GPU in {overlay_duration:.2f}s")
    
    return urls


def generate_overlay_urls(
    head_url: str,
    shapes: Iterable[str],
    stage: str,
    api_key: str,
    *,
    container: str,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
    use_cache: bool = True,
    user_id: Optional[int] = None,
) -> Dict[str, str]:
    """
    Generate overlay URLs - checks cache first, then uses Modal GPU or local CPU.
    """
    # Check cache if enabled and user_id provided
    if use_cache and user_id:
        try:
            # Import here to avoid circular dependency
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tg_bot.utils.user_state import get_cached_overlay_urls
            
            cached = get_cached_overlay_urls(user_id)
            if cached:
                # Check if all required shapes are in cache
                required_shapes = set(shapes)
                cached_shapes = set(cached.keys())
                
                if required_shapes.issubset(cached_shapes):
                    logger.info(f"[AUTOPIPELINE] ✅ Using cached overlay URLs: {list(cached.keys())}")
                    return {shape: cached[shape] for shape in required_shapes}
                else:
                    missing = required_shapes - cached_shapes
                    logger.info(f"[AUTOPIPELINE] ⚠️ Cache incomplete, missing shapes: {list(missing)}")
        except Exception as e:
            logger.warning(f"[AUTOPIPELINE] Failed to check overlay cache: {e}")
    
    # Continue with normal generation if no cache
    logger.info(f"[AUTOPIPELINE] Generating overlays (no cache)")
    
    # Check if Modal GPU service is configured
    modal_endpoint = os.getenv("MODAL_OVERLAY_ENDPOINT")
    
    if modal_endpoint:
        logger.info("[AUTOPIPELINE] 🚀 Using Modal GPU service for overlay generation")
        return generate_overlay_urls_modal(
            modal_endpoint,
            head_url,
            shapes,
            container=container,
            engine=engine,
            rembg_model=rembg_model,
            rembg_alpha_matting=rembg_alpha_matting,
            circle_radius=circle_radius,
            circle_center_x=circle_center_x,
            circle_center_y=circle_center_y,
        )
    
    # Fallback to local CPU processing
    logger.info("[AUTOPIPELINE] 💻 Using local CPU for overlay generation")
    
    urls: Dict[str, str] = {}
    shapes = set(shapes)
    if not shapes:
        return urls

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        for shape in shapes:
            output_name = f"overlay_{shape}.{'mov' if container == 'mov' else 'webm'}"
            output_path = tmpdir / output_name
            logger.info(f"[AUTOPIPELINE] ▶️ Preparing {shape} overlay")
            overlay_url = prepare_overlay.prepare_overlay(
                head_url,
                output_path,
                stage,
                api_key,
                container,
                threshold=0.6,
                feather=7,
                debug=False,
                engine=engine,
                rembg_model=rembg_model,
                rembg_alpha_matting=rembg_alpha_matting,
                rembg_fg_threshold=240,
                rembg_bg_threshold=10,
                rembg_erode_size=10,
                rembg_base_size=1000,
                shape=shape,
                circle_radius=circle_radius,
                circle_center_x=circle_center_x,
                circle_center_y=circle_center_y,
                circle_auto_center=getattr(args, 'circle_auto_center', True),
            )
            urls[shape] = overlay_url
    return urls


def download_to_temp(url: str, dest: Path) -> None:
    start_time = time.time()
    logger.info(f"[AUTOPIPELINE] ▶️ Downloading from URL")
    prepare_overlay.download_file(url, dest)
    
    file_size = dest.stat().st_size
    duration = time.time() - start_time
    size_mb = file_size / (1024 * 1024)
    
    logger.info(f"[AUTOPIPELINE] ⏱️ Downloaded {size_mb:.1f}MB in {duration:.2f}s")
    logger.info(f"[AUTOPIPELINE] 📊 Download speed: {size_mb / duration:.1f}MB/s")


def build_output_dir(explicit: Optional[str]) -> Path:
    if explicit:
        path = Path(explicit)
        path.mkdir(parents=True, exist_ok=True)
        return path
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = BUILD_ROOT / f"auto_{timestamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_specs(spec_paths: Iterable[Path]) -> Dict[str, Dict[str, object]]:
    results: Dict[str, Dict[str, object]] = {}
    for spec_path in spec_paths:
        start_time = time.time()
        logger.info(f"[AUTOPIPELINE] ▶️ Rendering spec: {spec_path.name}")
        
        result = assemble.render_from_spec(str(spec_path))
        
        duration = time.time() - start_time
        logger.info(f"[AUTOPIPELINE] ⏱️ Render completed in {duration:.2f}s")
        logger.info(f"[AUTOPIPELINE] 📊 Result URL: {result.get('url')}")
        
        results[spec_path.name] = result
    return results


def main() -> None:
    overall_start = time.time()
    logger.info(f"[AUTOPIPELINE] ▶️ Starting autopipeline")
    
    args = parse_args()

    templates = validate_templates(args.templates.split(","))
    logger.info(f"[AUTOPIPELINE] 📊 Templates to render: {', '.join(templates)}")
    
    api_key = os.getenv("SHOTSTACK_API_KEY")
    if not api_key:
        raise PipelineError("Не найден SHOTSTACK_API_KEY в окружении.")
    stage = os.getenv("SHOTSTACK_STAGE", assemble.DEFAULT_STAGE)
    logger.info(f"[AUTOPIPELINE] 📊 Shotstack stage: {stage}")

    required_shapes: set[str] = set()
    for template in templates:
        config = TEMPLATE_REGISTRY[template]
        overlay_nodes = config.get("overlay_nodes", {})
        if isinstance(overlay_nodes, dict):
            required_shapes.update(overlay_nodes.keys())
    
    if required_shapes:
        logger.info(f"[AUTOPIPELINE] 📊 Required overlay shapes: {', '.join(required_shapes)}")
    else:
        logger.info(f"[AUTOPIPELINE] 📊 No overlays required")

    transcript_text = read_transcript(args)
    if transcript_text:
        logger.info(f"[AUTOPIPELINE] 📊 Transcript provided: {len(transcript_text)} chars")

    start_time = time.time()
    if required_shapes:
        logger.info(f"[AUTOPIPELINE] ▶️ Generating overlays")
        logger.info(f"[AUTOPIPELINE] 📊 Overlay engine: {args.overlay_engine}")
        logger.info(f"[AUTOPIPELINE] 📊 Container: {args.overlay_container}")
    
    # Extract user_id from args if available
    user_id = args.user_id if hasattr(args, 'user_id') else None
    
    overlay_urls = generate_overlay_urls(
        head_url=args.head_url,
        shapes=required_shapes,
        stage=stage,
        api_key=api_key,
        container=args.overlay_container,
        engine=args.overlay_engine,
        rembg_model=args.rembg_model,
        rembg_alpha_matting=args.rembg_alpha_matting,
        circle_radius=args.circle_radius,
        circle_center_x=args.circle_center_x,
        circle_center_y=args.circle_center_y,
        use_cache=True,
        user_id=user_id,
    )
    
    # Log generated overlays for caching
    for shape, url in overlay_urls.items():
        logger.info(f"[AUTOPIPELINE] Generated overlay {shape}: {url}")
    
    if required_shapes:
        overlay_duration = time.time() - start_time
        if overlay_duration > 60:
            minutes = int(overlay_duration // 60)
            seconds = overlay_duration % 60
            logger.info(f"[AUTOPIPELINE] ⏱️ Overlays generated in {overlay_duration:.2f}s ({minutes}m {seconds:.1f}s) ⚠️")
        else:
            logger.info(f"[AUTOPIPELINE] ⏱️ Overlays generated in {overlay_duration:.2f}s")

    subtitles_from_file: Optional[List[Dict[str, object]]] = None
    if args.subtitles:
        subtitles_from_file = load_subtitles(args.subtitles)
        print(f"Загружено субтитров: {len(subtitles_from_file)}")
    auto_subtitles: Optional[List[Dict[str, object]]] = None
    blocks_config = load_blocks_config(args.blocks_config)
    intro_settings: Optional[Dict[str, Any]] = None
    outro_settings: Optional[Dict[str, Any]] = None

    if args.intro_url:
        templates_for_intro = set(parse_template_list(args.intro_templates, templates))
        intro_settings = {
            "clip": {
                "type": "video",
                "src": args.intro_url,
                "length": max(args.intro_length, 0.1),
                "fit": "contain",
                "transition": "fade",
            },
            "templates": templates_for_intro,
        }
    if args.outro_url:
        templates_for_outro = set(parse_template_list(args.outro_templates, templates))
        outro_settings = {
            "clip": {
                "type": "video",
                "src": args.outro_url,
                "length": max(args.outro_length, 0.1),
                "fit": "contain",
                "transition": "fade",
            },
            "templates": templates_for_outro,
        }

    head_duration = 0.0

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        
        # Скачивание фона
        logger.info(f"[AUTOPIPELINE] ▶️ Processing background video")
        bg_path = tmpdir / "background_source"
        download_to_temp(args.background_url, bg_path)
        
        start_time = time.time()
        width, height, duration = run_ffprobe_meta(bg_path)
        logger.info(f"[AUTOPIPELINE] ⏱️ ffprobe analyzed in {time.time() - start_time:.2f}s")
        logger.info(f"[AUTOPIPELINE] 📊 Background: {width}x{height} ({width/height:.3f}), {duration:.2f}s")
        
        fit_mode = decide_fit(width, height, args.fit_tolerance)
        logger.info(f"[AUTOPIPELINE] 📊 Fit mode: {fit_mode}")
        if fit_mode == "contain":
            logger.info(f"[AUTOPIPELINE] 📊 Using letterbox/pillarbox (no distortion)")

        # Скачивание головы
        logger.info(f"[AUTOPIPELINE] ▶️ Processing head video")
        head_path = tmpdir / "head_source"
        download_to_temp(args.head_url, head_path)
        
        start_time = time.time()
        _, _, head_duration = run_ffprobe_meta(head_path)
        logger.info(f"[AUTOPIPELINE] ⏱️ ffprobe analyzed in {time.time() - start_time:.2f}s")
        logger.info(f"[AUTOPIPELINE] 📊 Head duration: {head_duration:.2f}s")

        if transcript_text:
            logger.info(f"[AUTOPIPELINE] ▶️ Detecting speech segments")
            start_time = time.time()
            segments = detect_speech_segments(head_path, head_duration)
            logger.info(f"[AUTOPIPELINE] ⏱️ Speech detection in {time.time() - start_time:.2f}s")
            logger.info(f"[AUTOPIPELINE] 📊 Found {len(segments)} speech segments")
            
            logger.info(f"[AUTOPIPELINE] ▶️ Aligning transcript to segments")
            start_time = time.time()
            auto_subtitles = align_transcript_to_segments(transcript_text, segments, head_duration)
            logger.info(f"[AUTOPIPELINE] ⏱️ Aligned {len(auto_subtitles)} subtitles in {time.time() - start_time:.2f}s")

    output_dir = build_output_dir(args.output_dir)
    logger.info(f"[AUTOPIPELINE] 📊 Output directory: {output_dir}")

    written_specs: List[Path] = []
    summary: Dict[str, Dict[str, object]] = {}

    for template in templates:
        config = TEMPLATE_REGISTRY[template]
        file_path = Path(config["file"])  # type: ignore[index]
        if not file_path.exists():
            raise PipelineError(f"Не найден файл шаблона: {file_path}")
        with open(file_path, encoding="utf-8") as handle:
            spec = json.load(handle)

        if config.get("background_nodes"):
            update_nodes(spec, config["background_nodes"], args.background_url, fit_mode)  # type: ignore[arg-type]
        if config.get("head_nodes"):
            update_nodes(spec, config["head_nodes"], args.head_url, None)  # type: ignore[arg-type]
        overlay_nodes = config.get("overlay_nodes")
        if isinstance(overlay_nodes, dict):
            for shape, paths in overlay_nodes.items():
                overlay_url = overlay_urls.get(shape)
                if not overlay_url:
                    raise PipelineError(f"Для шаблона {template} нужен оверлей формы '{shape}', но URL не получен.")
                update_nodes(spec, paths, overlay_url, "contain")  # type: ignore[arg-type]

        if fit_mode == "contain":
            ensure_background(spec, args.background_color)

        if args.subtitles_enabled == "none":
            spec.pop("subtitles", None)
        elif args.subtitles_enabled == "manual":
            if subtitles_from_file is not None:
                spec["subtitles"] = copy.deepcopy(subtitles_from_file)
            else:
                spec.pop("subtitles", None)
        else:  # auto
            if subtitles_from_file is not None:
                spec["subtitles"] = copy.deepcopy(subtitles_from_file)
            elif transcript_text:
                spec["subtitles"] = auto_subtitles or []

        template_blocks = blocks_config.get(template, {})
        apply_blocks(spec, template_blocks, head_duration)

        cli_blocks: Dict[str, Any] = {}
        if intro_settings and template in intro_settings["templates"]:
            clip = copy.deepcopy(intro_settings["clip"])
            cli_blocks.setdefault("prepend_clips", []).append(clip)
        if outro_settings and template in outro_settings["templates"]:
            clip = copy.deepcopy(outro_settings["clip"])
            cli_blocks.setdefault("append_clips", []).append(clip)
        if cli_blocks:
            apply_blocks(spec, cli_blocks, head_duration)
        spec_path = output_dir / file_path.name
        with open(spec_path, "w", encoding="utf-8") as handle:
            json.dump(spec, handle, indent=2, ensure_ascii=False)
        written_specs.append(spec_path)

    if args.no_render:
        logger.info(f"[AUTOPIPELINE] ⏱️ Specs prepared (--no-render), skipping render")
        return

    logger.info(f"[AUTOPIPELINE] ▶️ Starting renders")
    try:
        render_start = time.time()
        summary = render_specs(written_specs)
        render_duration = time.time() - render_start
        logger.info(f"[AUTOPIPELINE] ⏱️ All renders completed in {render_duration:.2f}s")
    except assemble.ShotstackError as exc:
        raise PipelineError(f"Render завершился с ошибкой: {exc}") from exc

    logger.info(f"[AUTOPIPELINE] ✅ Results:")
    for name, result in summary.items():
        logger.info(f"[AUTOPIPELINE] - {name}: {result.get('url')}")
        # Также выводим в stdout для парсинга родительским процессом
        print(f"- {name}: {result.get('url')}")
    
    overall_duration = time.time() - overall_start
    minutes = int(overall_duration // 60)
    seconds = overall_duration % 60
    logger.info(f"[AUTOPIPELINE] ⏱️ Total autopipeline execution: {overall_duration:.2f}s ({minutes}m {seconds:.1f}s)")


if __name__ == "__main__":
    try:
        main()
    except PipelineError as exc:
        logger.error(f"[AUTOPIPELINE] ❌ Pipeline error: {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:
        logger.error(f"[AUTOPIPELINE] ❌ Unexpected error: {exc}", exc_info=True)
        raise SystemExit(1) from exc
