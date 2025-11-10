from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, Iterable, Type

import prepare_overlay


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
    timed_step=None,
    error_cls: Type[Exception] = RuntimeError,
    auto_circle_center: bool = True,
) -> Dict[str, str]:
    urls: Dict[str, str] = {}
    shapes = set(shapes)
    if not shapes:
        return urls

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        for shape in shapes:
            output_name = f"overlay_{shape}.{'mov' if container == 'mov' else 'webm'}"
            output_path = tmpdir / output_name
            step_ctx = timed_step if timed_step is not None else _nullcontext
            with step_ctx(f"Подготовка оверлея {shape}"):
                try:
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
                        circle_auto_center=auto_circle_center,
                    )
                except Exception as exc:
                    raise error_cls(f"Не удалось подготовить оверлей формы '{shape}': {exc}") from exc
            urls[shape] = overlay_url
    return urls


class _nullcontext:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def download_to_temp(url: str, dest: Path, *, error_cls: Type[Exception] = RuntimeError) -> None:
    print(f"Скачиваем {url}...")
    try:
        prepare_overlay.download_file(url, dest)
    except Exception as exc:
        raise error_cls(f"Не удалось скачать файл: {url}") from exc
