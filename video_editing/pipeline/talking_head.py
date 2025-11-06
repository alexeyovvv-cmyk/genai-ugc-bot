"""
Core logic for the talking-head automation pipeline.
"""
from __future__ import annotations

import copy
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from common.media import MediaMeta, decide_fit, run_ffprobe_meta, sniff_remote_media_type
from overlay import download_to_temp, generate_overlay_urls
from render.shotstack import DEFAULT_STAGE, ShotstackError, render_from_spec
from render.subtitle import subtitle_tools
from render.templates import ensure_background, get_node, load_spec, save_spec, update_nodes
from render.timeline import apply_blocks, load_blocks_config

DEFAULT_FIT_TOLERANCE = 0.02
BUILD_ROOT = Path("build")


class PipelineError(RuntimeError):
    """Raised for any automation failure."""


@contextmanager
def timed_step(description: str) -> Iterator[None]:
    print(f"--> {description}")
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"<-- {description}: {elapsed:.2f}s")


TEMPLATE_REGISTRY: Dict[str, Dict[str, object]] = {
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


def parse_template_list(raw: Optional[str], default: Sequence[str]) -> List[str]:
    if raw is None:
        return list(default)
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or list(default)


def validate_templates(names: Iterable[str]) -> List[str]:
    valid: List[str] = []
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
        with timed_step(f"Рендер {spec_path.name}"):
            result = render_from_spec(str(spec_path))
        results[spec_path.name] = result
        print(f"Готово: {result.get('url')}")
    return results


def _safe_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _estimate_clip_end(clip: Dict[str, Any], fallback_duration: float) -> float:
    """
    Approximate момент окончания клипа: старт + (length | длительность из метаданных - trim).
    Используется до shotstack-автоматизации, когда length может быть не заполнен.
    """
    start = _safe_float(clip.get("start", 0.0))
    length = clip.get("length")
    if isinstance(length, (int, float)):
        try:
            duration = max(float(length), 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        return start + duration

    trim = _safe_float(clip.get("trim", 0.0))
    effective_fallback = max(fallback_duration - trim, 0.0)
    return start + effective_fallback


def _track_end(entries: Iterable[Dict[str, Any]], target_end: float) -> float:
    end = 0.0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            start = float(entry.get("start", 0.0) or 0.0)
        except (TypeError, ValueError):
            start = 0.0

        length_value = entry.get("length")
        duration: float
        if isinstance(length_value, (int, float)):
            try:
                duration = max(float(length_value), 0.0)
            except (TypeError, ValueError):
                duration = 0.0
            end_candidate = start + duration
        elif entry.get("auto_length") or entry.get("match_length_to"):
            end_candidate = max(target_end, start)
        else:
            fallback_duration = max(target_end - start, 0.0)
            end_candidate = _estimate_clip_end(entry, fallback_duration)

        end = max(end, end_candidate)
    return end


def _subtitles_end(subtitles: Iterable[Dict[str, Any]]) -> float:
    end = 0.0
    for subtitle in subtitles:
        if not isinstance(subtitle, dict):
            continue
        try:
            start = float(subtitle.get("start", 0.0) or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        length = subtitle.get("length")
        try:
            duration = max(float(length), 0.0) if isinstance(length, (int, float)) else 0.0
        except (TypeError, ValueError):
            duration = 0.0
        end = max(end, start + duration)
    return end


def _lock_auto_length(entries: Iterable[Dict[str, Any]], target_end: float) -> None:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not entry.get("auto_length") and not entry.get("match_length_to"):
            continue
        try:
            start = float(entry.get("start", 0.0) or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        desired_length = max(target_end - start, 0.0)
        entry["length"] = round(max(desired_length, 0.001), 3)
        entry.pop("auto_length", None)
        entry.pop("match_length_to", None)
        entry.pop("speed", None)


class TalkingHeadPipeline:
    def __init__(
        self,
        args,
        *,
        overlay_provider: Optional[Callable[[Iterable[str]], Dict[str, str]]] = None,
    ) -> None:
        self.args = args
        self.templates = validate_templates(args.templates.split(","))
        self.api_key = os.getenv("SHOTSTACK_API_KEY")
        if not self.api_key:
            raise PipelineError("Не найден SHOTSTACK_API_KEY в окружении.")
        self.stage = os.getenv("SHOTSTACK_STAGE", DEFAULT_STAGE)
        self.blocks_config = load_blocks_config(args.blocks_config, error_cls=PipelineError)
        self.required_shapes = self._collect_required_shapes()
        self.transcript_text = subtitle_tools.read_transcript(
            args.transcript,
            args.transcript_file,
            error_cls=PipelineError,
        )
        self.circle_auto_center = getattr(args, "circle_auto_center", True)
        self.background_video_mode = getattr(args, "background_video_length", "auto")
        self.output_dir = build_output_dir(args.output_dir)
        print(f"Спецификации будут сохранены в {self.output_dir}")
        self.overlay_provider = overlay_provider

    def _collect_required_shapes(self) -> set[str]:
        shapes: set[str] = set()
        for template in self.templates:
            config = TEMPLATE_REGISTRY[template]
            overlay_nodes = config.get("overlay_nodes", {})
            if isinstance(overlay_nodes, dict):
                shapes.update(overlay_nodes.keys())
        return shapes

    def _generate_overlay_urls(self) -> Dict[str, str]:
        with timed_step("Генерация оверлеев"):
            return generate_overlay_urls(
                head_url=self.args.head_url,
                shapes=self.required_shapes,
                stage=self.stage,
                api_key=self.api_key,
                container=self.args.overlay_container,
                engine=self.args.overlay_engine,
                rembg_model=self.args.rembg_model,
                rembg_alpha_matting=self.args.rembg_alpha_matting,
                circle_radius=self.args.circle_radius,
                circle_center_x=self.args.circle_center_x,
                circle_center_y=self.args.circle_center_y,
                timed_step=timed_step,
                error_cls=PipelineError,
                auto_circle_center=self.circle_auto_center,
            )

    def _load_manual_subtitles(self) -> Optional[List[Dict[str, object]]]:
        if not self.args.subtitles:
            return None
        subtitles = subtitle_tools.load_subtitles(self.args.subtitles, error_cls=PipelineError)
        print(f"Загружено субтитров: {len(subtitles)}")
        return subtitles

    def _prepare_media(self) -> Tuple[MediaMeta, float, str, Optional[List[Dict[str, object]]]]:
        auto_subtitles: Optional[List[Dict[str, object]]] = None
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            bg_path = tmpdir / "background_source"
            with timed_step("Скачивание фона"):
                download_to_temp(self.args.background_url, bg_path, error_cls=PipelineError)
            with timed_step("Анализ фона (ffprobe)"):
                background_meta = run_ffprobe_meta(bg_path, error_cls=PipelineError)

            fit_mode = decide_fit(background_meta.width, background_meta.height, self.args.fit_tolerance)
            aspect_ratio = background_meta.width / background_meta.height if background_meta.height else 0.0
            if background_meta.asset_type == "image":
                print(
                    f"Аспект фона {background_meta.width}x{background_meta.height} ({aspect_ratio:.3f}), "
                    f"статичное изображение. Выбран fit={fit_mode}."
                )
            else:
                print(
                    f"Аспект фона {background_meta.width}x{background_meta.height} ({aspect_ratio:.3f}), "
                    f"длительность {background_meta.duration:.2f}s. Выбран fit={fit_mode}."
                )
            if fit_mode == "contain":
                print("Используем подложку и fit=contain, искажений не будет.")

            head_path = tmpdir / "head_source"
            with timed_step("Скачивание говорящей головы"):
                download_to_temp(self.args.head_url, head_path, error_cls=PipelineError)
            with timed_step("Анализ говорящей головы (ffprobe)"):
                head_meta = run_ffprobe_meta(head_path, error_cls=PipelineError)
            if head_meta.asset_type != "video":
                raise PipelineError("Говорящая голова должна быть видео.")

            if self.transcript_text:
                with timed_step("Анализ речи и авто-субтитры"):
                    segments = subtitle_tools.detect_speech_segments(
                        head_path,
                        head_meta.duration,
                        error_cls=PipelineError,
                    )
                    auto_subtitles = subtitle_tools.align_transcript_to_segments(
                        self.transcript_text,
                        segments,
                        head_meta.duration,
                    )
                print(f"Автоматически создано субтитров: {len(auto_subtitles)}")

        return background_meta, head_meta.duration, fit_mode, auto_subtitles

    def _prepare_cli_blocks(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, float]]:
        intro_settings: Optional[Dict[str, Any]] = None
        outro_settings: Optional[Dict[str, Any]] = None

        if self.args.intro_url:
            templates_for_intro = set(parse_template_list(self.args.intro_templates, self.templates))
            intro_type = sniff_remote_media_type(self.args.intro_url, error_cls=PipelineError)
            intro_clip: Dict[str, Any] = {
                "type": intro_type,
                "src": self.args.intro_url,
                "length": max(self.args.intro_length, 0.1),
                "fit": "contain",
                "transition": "fade",
            }
            intro_settings = {"clip": intro_clip, "templates": templates_for_intro}

        if self.args.outro_url:
            templates_for_outro = set(parse_template_list(self.args.outro_templates, self.templates))
            outro_type = sniff_remote_media_type(self.args.outro_url, error_cls=PipelineError)
            outro_clip: Dict[str, Any] = {
                "type": outro_type,
                "src": self.args.outro_url,
                "length": max(self.args.outro_length, 0.1),
                "fit": "contain",
                "transition": "fade",
            }
            outro_settings = {"clip": outro_clip, "templates": templates_for_outro}

        intro_lengths_by_template: Dict[str, float] = {}
        if intro_settings:
            intro_len = float(intro_settings["clip"]["length"])
            for tmpl in intro_settings["templates"]:
                intro_lengths_by_template[tmpl] = intro_lengths_by_template.get(tmpl, 0.0) + intro_len

        return intro_settings, outro_settings, intro_lengths_by_template

    def _build_cli_blocks_for_template(
        self,
        template: str,
        intro_settings: Optional[Dict[str, Any]],
        outro_settings: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        cli_blocks: Dict[str, Any] = {}
        if intro_settings and template in intro_settings["templates"]:
            clip = copy.deepcopy(intro_settings["clip"])
            cli_blocks.setdefault("prepend_clips", []).append(clip)
        if outro_settings and template in outro_settings["templates"]:
            clip = copy.deepcopy(outro_settings["clip"])
            cli_blocks.setdefault("append_clips", []).append(clip)
        return cli_blocks

    def _prepare_single_template(
        self,
        template: str,
        background_meta: MediaMeta,
        head_duration: float,
        fit_mode: str,
        overlay_urls: Dict[str, str],
        subtitles_from_file: Optional[List[Dict[str, object]]],
        auto_subtitles: Optional[List[Dict[str, object]]],
        intro_settings: Optional[Dict[str, Any]],
        outro_settings: Optional[Dict[str, Any]],
        intro_lengths_by_template: Dict[str, float],
    ) -> Path:
        config = TEMPLATE_REGISTRY[template]
        file_path = Path(config["file"])  # type: ignore[index]
        if not file_path.exists():
            raise PipelineError(f"Не найден файл шаблона: {file_path}")

        spec = load_spec(file_path)
        max_content_end = 0.0

        head_entries: List[Dict[str, Any]] = []
        if config.get("head_nodes"):
            update_nodes(
                spec,
                config["head_nodes"],
                self.args.head_url,
                None,
                error_cls=PipelineError,
            )  # type: ignore[arg-type]
            for path in config["head_nodes"]:
                clip = get_node(spec, path, error_cls=PipelineError)
                head_entries.append(clip)
            if head_entries:
                head_max_end = _track_end(head_entries, head_duration)
                if head_max_end > 0.0:
                    max_content_end = max(max_content_end, head_max_end)

        background_entries: List[Dict[str, Any]] = []
        if config.get("background_nodes"):
            update_nodes(
                spec,
                config["background_nodes"],
                self.args.background_url,
                fit_mode,
                error_cls=PipelineError,
                asset_type=background_meta.asset_type,
            )  # type: ignore[arg-type]
            for path in config["background_nodes"]:
                clip = get_node(spec, path, error_cls=PipelineError)
                background_entries.append(clip)
            if background_entries:
                if background_meta.asset_type == "video" and self.background_video_mode == "fixed":
                    for clip in background_entries:
                        clip.pop("match_length_to", None)
                        clip.pop("auto_length", None)
                        clip.pop("speed", None)
                        length_value = max(background_meta.duration - _safe_float(clip.get("trim", 0.0)), 0.0)
                        clip["length"] = round(max(length_value, 0.1), 3)
                target_end = max_content_end if max_content_end > 0.0 else head_duration
                if background_meta.asset_type == "video" and self.background_video_mode == "fixed":
                    target_end = max(
                        target_end,
                        max(
                            _safe_float(clip.get("start", 0.0)) + max(
                                background_meta.duration - _safe_float(clip.get("trim", 0.0)),
                                0.0,
                            )
                            for clip in background_entries
                        ),
                    )
                background_max_end = _track_end(background_entries, target_end)
                if background_max_end > 0.0:
                    max_content_end = max(max_content_end, background_max_end)

        overlay_nodes = config.get("overlay_nodes")
        if isinstance(overlay_nodes, dict):
            for shape, paths in overlay_nodes.items():
                overlay_url = overlay_urls.get(shape)
                if not overlay_url:
                    raise PipelineError(f"Для шаблона {template} нужен оверлей формы '{shape}', но URL не получен.")
                update_nodes(
                    spec,
                    paths,
                    overlay_url,
                    "contain",
                    error_cls=PipelineError,
                )  # type: ignore[arg-type]

        if fit_mode == "contain":
            ensure_background(spec, self.args.background_color)

        if self.args.subtitles_enabled == "none":
            spec.pop("subtitles", None)
        elif self.args.subtitles_enabled == "manual":
            if subtitles_from_file is not None:
                spec["subtitles"] = copy.deepcopy(subtitles_from_file)
            else:
                spec.pop("subtitles", None)
        else:  # auto
            if subtitles_from_file is not None:
                spec["subtitles"] = copy.deepcopy(subtitles_from_file)
            elif self.transcript_text:
                spec["subtitles"] = auto_subtitles or []

        if max_content_end <= 0.0:
            max_content_end = head_duration

        fallback_length = max_content_end or head_duration
        clips_end = _track_end(spec.get("clips", []), fallback_length)
        overlays_end = _track_end(spec.get("overlays", []), fallback_length)
        subtitles_end = _subtitles_end(spec.get("subtitles", []))
        actual_end = max(clips_end, overlays_end, subtitles_end)
        if actual_end > 0.0:
            max_content_end = max(max_content_end, actual_end)

        _lock_auto_length(spec.get("clips", []), max_content_end)

        template_blocks = self.blocks_config.get(template, {})
        apply_blocks(spec, template_blocks, max_content_end, error_cls=PipelineError)

        cli_blocks = self._build_cli_blocks_for_template(template, intro_settings, outro_settings)
        if cli_blocks:
            apply_blocks(spec, cli_blocks, max_content_end, error_cls=PipelineError)

        spec["subtitle_theme"] = self.args.subtitle_theme

        if config.get("background_nodes") and background_meta.asset_type == "image":
            intro_total = intro_lengths_by_template.get(template, 0.0)
            main_length = max(head_duration, 0.1)
            main_end = intro_total + main_length
            for path in config["background_nodes"]:
                clip = get_node(spec, path, error_cls=PipelineError)
                try:
                    clip_start = float(clip.get("start", 0.0) or 0.0)
                except (TypeError, ValueError):
                    clip_start = 0.0
                desired_end = main_end if clip_start < main_end else clip_start
                desired_length = max(desired_end - clip_start, 0.0)
                clip["length"] = round(max(desired_length, 0.1), 3)

        spec_path = self.output_dir / file_path.name
        save_spec(spec, spec_path)
        return spec_path

    def _prepare_templates(
        self,
        background_meta: MediaMeta,
        head_duration: float,
        fit_mode: str,
        overlay_urls: Dict[str, str],
        subtitles_from_file: Optional[List[Dict[str, object]]],
        auto_subtitles: Optional[List[Dict[str, object]]],
        intro_settings: Optional[Dict[str, Any]],
        outro_settings: Optional[Dict[str, Any]],
        intro_lengths_by_template: Dict[str, float],
    ) -> List[Path]:
        written_specs: List[Path] = []
        for template in self.templates:
            with timed_step(f"Подготовка шаблона {template}"):
                spec_path = self._prepare_single_template(
                    template,
                    background_meta,
                    head_duration,
                    fit_mode,
                    overlay_urls,
                    subtitles_from_file,
                    auto_subtitles,
                    intro_settings,
                    outro_settings,
                    intro_lengths_by_template,
                )
                written_specs.append(spec_path)
        return written_specs

    def run(self) -> Optional[Dict[str, Dict[str, object]]]:
        if self.overlay_provider:
            with timed_step("Генерация оверлеев"):
                overlay_urls = self.overlay_provider(self.required_shapes)
        else:
            overlay_urls = self._generate_overlay_urls()
        subtitles_from_file = self._load_manual_subtitles()
        background_meta, head_duration, fit_mode, auto_subtitles = self._prepare_media()
        intro_settings, outro_settings, intro_lengths_by_template = self._prepare_cli_blocks()

        written_specs = self._prepare_templates(
            background_meta,
            head_duration,
            fit_mode,
            overlay_urls,
            subtitles_from_file,
            auto_subtitles,
            intro_settings,
            outro_settings,
            intro_lengths_by_template,
        )

        if self.args.no_render:
            print("Рендер отключён (--no-render). Спецификации готовы.")
            return None

        try:
            with timed_step("Рендер всех спецификаций"):
                summary = render_specs(written_specs)
        except ShotstackError as exc:
            raise PipelineError(f"Render завершился с ошибкой: {exc}") from exc

        print("\nРезультаты:")
        for name, result in summary.items():
            print(f"- {name}: {result.get('url')}")
        return summary
