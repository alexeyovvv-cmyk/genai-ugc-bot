#!/usr/bin/env python3
"""
CLI-обёртка над TalkingHeadPipeline с сохранением истории старого интерфейса.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

from overlay import builder as overlay_builder
from pipeline import DEFAULT_FIT_TOLERANCE, PipelineError, TalkingHeadPipeline
from render.shotstack import DEFAULT_STAGE

# Настройка логгера в том же формате, что и прежняя версия.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate the talking-head workflow end-to-end.")
    parser.add_argument("--background-url", required=True, help="Ссылка на фон (скринкаст).")
    parser.add_argument("--head-url", required=True, help="Ссылка на исходник говорящей головы.")
    parser.add_argument(
        "--templates",
        default="mix_basic_circle",
        help="Список шаблонов через запятую (overlay|circle|basic|mix_basic_overlay|mix_basic_circle). По умолчанию рендерится mix_basic_circle.",
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
        "--no-circle-auto-center",
        action="store_false",
        dest="circle_auto_center",
        help="Отключить авто-центровку круга и использовать заданные вручную координаты.",
    )
    parser.set_defaults(circle_auto_center=True)
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
        "--background-video-length",
        choices=["auto", "fixed"],
        default="auto",
        help="Поведение для видеофона: auto — подогнать длительность под голову, fixed — оставить как в исходнике.",
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
        "--subtitle-theme",
        choices=["light", "yellow_on_black", "white_on_purple"],
        default="light",
        help="Цветовая схема субтитров: light (по умолчанию), yellow_on_black или white_on_purple.",
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
        "--user-id",
        type=int,
        help="User ID для повторного использования кеша оверлеев.",
    )
    return parser.parse_args()


def _import_from_tg_bot(module: str, name: str):
    """Добавить корень проекта в sys.path и импортировать указанный объект."""
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    module_obj = __import__(module, fromlist=[name])
    return getattr(module_obj, name)


def _generate_overlays_via_modal(
    modal_endpoint: str,
    head_url: str,
    shapes: Set[str],
    *,
    container: str,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
    circle_auto_center: bool,
) -> Dict[str, str]:
    ModalOverlayClient = _import_from_tg_bot("tg_bot.services.modal_client", "ModalOverlayClient")  # type: ignore[var-annotated]

    client = ModalOverlayClient(base_url=modal_endpoint, poll_interval=5, timeout=600)
    urls: Dict[str, str] = {}

    overlay_start = time.time()
    for shape in shapes:
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
                circle_auto_center=circle_auto_center,
                threshold=0.6,
                feather=7,
                rembg_fg_threshold=240,
                rembg_bg_threshold=10,
                rembg_erode_size=10,
                rembg_base_size=1000,
            )
        except Exception as exc:  # pragma: no cover - сеть/Modal
            logger.error(f"[AUTOPIPELINE] ❌ Modal GPU failed for {shape}: {exc}")
            raise PipelineError(f"Modal GPU overlay generation failed: {exc}") from exc

        urls[shape] = overlay_url
        logger.info(f"[AUTOPIPELINE] ✅ {shape} overlay ready")

    overlay_duration = time.time() - overlay_start
    logger.info(f"[AUTOPIPELINE] ⏱️ Overlays generated via Modal GPU in {overlay_duration:.2f}s")
    return urls


def build_overlay_provider(args: argparse.Namespace, api_key: str, stage: str):
    """Сконструировать провайдер оверлеев с поддержкой кеша и Modal."""
    modal_endpoint = os.getenv("MODAL_OVERLAY_ENDPOINT")

    def provider(required_shapes: Iterable[str]) -> Dict[str, str]:
        shapes = {shape for shape in required_shapes if shape}
        if not shapes:
            return {}

        # Попытка загрузить кеш
        cached_urls: Optional[Dict[str, str]] = None
        if getattr(args, "user_id", None):
            try:
                get_cached_overlay_urls = _import_from_tg_bot("tg_bot.utils.user_state", "get_cached_overlay_urls")
                cached_urls = get_cached_overlay_urls(args.user_id)  # type: ignore[misc]
            except Exception as exc:  # pragma: no cover - кеш опционален
                logger.warning(f"[AUTOPIPELINE] Failed to check overlay cache: {exc}")
            else:
                if cached_urls:
                    cached_shapes = set(cached_urls.keys())
                    if shapes.issubset(cached_shapes):
                        logger.info(f"[AUTOPIPELINE] ✅ Using cached overlay URLs: {list(shapes)}")
                        for shape in shapes:
                            logger.info(f"[AUTOPIPELINE] Generated overlay {shape}: {cached_urls[shape]}")
                        return {shape: cached_urls[shape] for shape in shapes}
                    missing = shapes - cached_shapes
                    if missing:
                        logger.info(f"[AUTOPIPELINE] ⚠️ Cache incomplete, missing shapes: {list(missing)}")

        logger.info("[AUTOPIPELINE] Generating overlays (no cache)")
        start_time = time.time()

        if modal_endpoint:
            urls = _generate_overlays_via_modal(
                modal_endpoint,
                head_url=args.head_url,
                shapes=shapes,
                container=args.overlay_container,
                engine=args.overlay_engine,
                rembg_model=args.rembg_model,
                rembg_alpha_matting=args.rembg_alpha_matting,
                circle_radius=args.circle_radius,
                circle_center_x=args.circle_center_x,
                circle_center_y=args.circle_center_y,
                circle_auto_center=getattr(args, "circle_auto_center", True),
            )
        else:
            urls = overlay_builder.generate_overlay_urls(
                head_url=args.head_url,
                shapes=shapes,
                stage=stage,
                api_key=api_key,
                container=args.overlay_container,
                engine=args.overlay_engine,
                rembg_model=args.rembg_model,
                rembg_alpha_matting=args.rembg_alpha_matting,
                circle_radius=args.circle_radius,
                circle_center_x=args.circle_center_x,
                circle_center_y=args.circle_center_y,
                auto_circle_center=getattr(args, "circle_auto_center", True),
            )
            duration = time.time() - start_time
            logger.info(f"[AUTOPIPELINE] ⏱️ Overlays generated in {duration:.2f}s")

        for shape in shapes:
            url = urls.get(shape)
            if url:
                logger.info(f"[AUTOPIPELINE] Generated overlay {shape}: {url}")
        return urls

    return provider


def main() -> None:
    overall_start = time.time()
    logger.info("[AUTOPIPELINE] ▶️ Starting autopipeline")

    args = parse_args()
    logger.info(f"[AUTOPIPELINE] 📊 Templates to render: {args.templates}")
    logger.info(f"[AUTOPIPELINE] 📊 Overlay engine: {args.overlay_engine}")

    api_key = os.getenv("SHOTSTACK_API_KEY")
    if not api_key:
        raise PipelineError("Не найден SHOTSTACK_API_KEY в окружении.")
    stage = os.getenv("SHOTSTACK_STAGE", DEFAULT_STAGE)
    logger.info(f"[AUTOPIPELINE] 📊 Shotstack stage: {stage}")

    overlay_provider = build_overlay_provider(args, api_key, stage)
    pipeline = TalkingHeadPipeline(args, overlay_provider=overlay_provider)
    pipeline.run()

    overall_duration = time.time() - overall_start
    minutes = int(overall_duration // 60)
    seconds = overall_duration % 60
    logger.info(f"[AUTOPIPELINE] ⏱️ Total autopipeline execution: {overall_duration:.2f}s ({minutes}m {seconds:.1f}s)")


if __name__ == "__main__":
    try:
        main()
    except PipelineError as exc:
        logger.error(f"[AUTOPIPELINE] ❌ Pipeline error: {exc}")
        print(f"Ошибка: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:  # pragma: no cover - непредвиденные ошибки
        logger.error(f"[AUTOPIPELINE] ❌ Unexpected error: {exc}", exc_info=True)
        print(f"Ошибка: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
