#!/usr/bin/env python3
"""
Generate an alpha-matted talking head video and upload it to Shotstack ingest.

Requires:
    - mediapipe
    - opencv-python
    - numpy
    - requests
    - ffmpeg binary on PATH

Usage:
    SHOTSTACK_API_KEY=... python prepare_overlay.py \
        --input-url https://drive.usercontent.google.com/... \
        --stage stage \
        --output talking_head_alpha.webm

The script will:
    1. Download the source clip.
    2. Run Mediapipe selfie segmentation to remove the background.
    3. Export a WebM (VP9 + alpha) preserving audio.
    4. Upload the file using Shotstack ingest signed URLs.
    5. Wait until the processed asset is publicly reachable and print the URL.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import cv2  # type: ignore
import mediapipe as mp  # type: ignore
import numpy as np
import requests
from PIL import Image  # type: ignore

try:
    from rembg import new_session, remove  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for rembg engine
    new_session = None  # type: ignore
    remove = None  # type: ignore


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(["ffmpeg", "-y", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def download_file(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                handle.write(chunk)


def build_alpha_clip(
    source_path: Path,
    frames_dir: Path,
    audio_path: Path,
    alpha_video_path: Path,
    container: str,
    threshold: float,
    feather: int,
    debug: bool,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    rembg_fg_threshold: int,
    rembg_bg_threshold: int,
    rembg_erode_size: int,
    rembg_base_size: int,
    shape: str,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
) -> float:
    cap = cv2.VideoCapture(str(source_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    segmentation: Optional[mp.solutions.selfie_segmentation.SelfieSegmentation] = None
    rembg_session = None
    if engine == "mediapipe":
        segmentation = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
    elif engine == "rembg":
        if new_session is None or remove is None:
            raise RuntimeError("rembg is not installed. Run `pip install rembg onnxruntime Pillow` to enable this engine.")
        rembg_session = new_session(model_name=rembg_model)
    else:
        raise ValueError(f"Unsupported engine: {engine}")

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    feather = max(0, feather)
    if feather % 2 == 0 and feather != 0:
        feather += 1

    index = 0
    while True:
        success, frame = cap.read()
        if not success:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if engine == "mediapipe":
            assert segmentation is not None
            mask = segmentation.process(rgb).segmentation_mask.astype(np.float32)
        else:
            assert rembg_session is not None
            mask_image = remove(
                Image.fromarray(rgb),
                session=rembg_session,
                only_mask=True,
                alpha_matting=rembg_alpha_matting,
                alpha_matting_foreground_threshold=rembg_fg_threshold,
                alpha_matting_background_threshold=rembg_bg_threshold,
                alpha_matting_erode_structure_size=rembg_erode_size,
                alpha_matting_base_size=rembg_base_size,
            )
            mask = np.asarray(mask_image, dtype=np.float32) / 255.0

        mask = np.clip(mask, 0.0, 1.0)
        binary = (mask >= threshold).astype(np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        refined_mask = mask * binary
        alpha_float = np.clip(refined_mask, 0.0, 1.0)
        if feather:
            alpha_float = cv2.GaussianBlur(alpha_float, (feather, feather), 0)
        if shape == "circle":
            h, w = alpha_float.shape
            radius = max(0.0, min(1.0, circle_radius)) * float(min(w, h))
            cx = np.clip(circle_center_x, 0.0, 1.0) * (w - 1)
            cy = np.clip(circle_center_y, 0.0, 1.0) * (h - 1)
            yy, xx = np.ogrid[:h, :w]
            circle_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) <= radius ** 2
            alpha_float = alpha_float * circle_mask.astype(np.float32)

        alpha = np.clip(alpha_float * 255.0, 0, 255).astype(np.uint8)

        if debug and index == 0:
            print("Mask stats min/max/mean:", float(mask.min()), float(mask.max()), float(mask.mean()))
            print("Foreground coverage:", float((alpha > 0).mean()))

        foreground = (frame.astype(np.float32) * alpha_float[..., None]).astype(np.uint8)
        foreground_bgra = cv2.cvtColor(foreground, cv2.COLOR_BGR2BGRA)
        foreground_bgra[:, :, 3] = alpha

        out_path = frames_dir / f"frame_{index:04d}.png"
        cv2.imwrite(str(out_path), foreground_bgra)
        index += 1

    if segmentation is not None:
        segmentation.close()
    cap.release()

    if index == 0:
        raise RuntimeError("No frames extracted from source video.")

    # Extract audio using ffmpeg (copy codec if possible)
    run_ffmpeg(["-i", str(source_path), "-vn", "-acodec", "copy", str(audio_path)])

    frame_pattern = str(frames_dir / "frame_%04d.png")
    if container == "webm":
        encode_args = [
            "-framerate",
            f"{fps}",
            "-i",
            frame_pattern,
            "-i",
            str(audio_path),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-auto-alt-ref",
            "0",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
            str(alpha_video_path),
        ]
    else:
        encode_args = [
            "-framerate",
            f"{fps}",
            "-i",
            frame_pattern,
            "-i",
            str(audio_path),
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4444",
            "-pix_fmt",
            "yuva444p10le",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(alpha_video_path),
        ]

    run_ffmpeg(encode_args)

    duration = index / fps
    return duration


def request_signed_upload(api_key: str, stage: str) -> Tuple[str, str]:
    url = f"https://api.shotstack.io/ingest/{stage}/upload"
    response = requests.post(url, headers={"x-api-key": api_key}, timeout=30)
    response.raise_for_status()
    data = response.json()["data"]
    return data["id"], data["attributes"]["url"]


def upload_to_signed_url(file_path: Path, signed_url: str) -> None:
    with open(file_path, "rb") as handle:
        resp = requests.put(signed_url, data=handle, timeout=300)
    resp.raise_for_status()


def derive_public_url(signed_url: str, extension: str) -> Tuple[str, str]:
    parsed = urlparse(signed_url)
    segments = parsed.path.strip("/").split("/")
    if len(segments) < 3:
        raise ValueError(f"Unexpected signed URL structure: {signed_url}")
    owner_id, upload_id = segments[0], segments[1]
    base = f"{parsed.scheme}://{parsed.netloc}/{owner_id}/{upload_id}"
    return owner_id, f"{base}/source{extension}"


def wait_for_asset(url: str, timeout: int = 300, delay: float = 5.0) -> None:
    elapsed = 0.0
    while elapsed < timeout:
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(delay)
        elapsed += delay
    raise TimeoutError(f"Asset was not accessible within {timeout} seconds: {url}")


def prepare_overlay(
    input_url: str,
    output_path: Path,
    stage: str,
    api_key: str,
    container: str,
    threshold: float,
    feather: int,
    debug: bool,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    rembg_fg_threshold: int,
    rembg_bg_threshold: int,
    rembg_erode_size: int,
    rembg_base_size: int,
    shape: str,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
) -> str:
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        source_path = tmpdir / "input.mp4"
        frames_dir = tmpdir / "frames"
        frames_dir.mkdir()
        audio_path = tmpdir / "audio.m4a"

        print("Downloading source clip...")
        download_file(input_url, source_path)

        print(f"Building alpha-matted clip using {engine}...")
        duration = build_alpha_clip(
            source_path,
            frames_dir,
            audio_path,
            output_path,
            container,
            threshold,
            feather,
            debug,
            engine,
            rembg_model,
            rembg_alpha_matting,
            rembg_fg_threshold,
            rembg_bg_threshold,
            rembg_erode_size,
            rembg_base_size,
            shape,
            circle_radius,
            circle_center_x,
            circle_center_y,
        )
        extension = output_path.suffix or (".webm" if container == "webm" else ".mov")

        print("Requesting Shotstack signed upload URL...")
        upload_id, signed_url = request_signed_upload(api_key, stage)
        print(f"Upload ID: {upload_id}")

        print("Uploading alpha clip to Shotstack ingest...")
        upload_to_signed_url(output_path, signed_url)

        print("Deriving public asset URL...")
        _, public_url = derive_public_url(signed_url, extension)

        print("Waiting for Shotstack to process the uploaded asset...")
        wait_for_asset(public_url)

        print(f"Overlay ready at {public_url} (duration {duration:.2f}s)")
        return public_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a talking-head overlay with alpha and upload to Shotstack.")
    parser.add_argument("--input-url", required=True, help="Public URL to the source talking-head video.")
    parser.add_argument(
        "--output",
        default="talking_head_alpha.webm",
        help="Path to save the alpha clip (extension determines container).",
    )
    parser.add_argument(
        "--container",
        choices=["webm", "mov"],
        default=os.getenv("OVERLAY_CONTAINER", "mov"),
        help="Output container/codec for the alpha clip (default: mov/prores).",
    )
    parser.add_argument(
        "--engine",
        choices=["mediapipe", "rembg"],
        default=os.getenv("OVERLAY_ENGINE", "mediapipe"),
        help="Background removal engine to use (default: mediapipe).",
    )
    parser.add_argument(
        "--stage",
        choices=["stage", "production"],
        default=os.getenv("SHOTSTACK_STAGE", "stage"),
        help="Shotstack environment stage (default: stage).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("OVERLAY_THRESHOLD", "0.6")),
        help="Segmentation threshold between 0 and 1 (higher removes more background, default: 0.6).",
    )
    parser.add_argument(
        "--feather",
        type=int,
        default=int(os.getenv("OVERLAY_FEATHER", "7")),
        help="Gaussian blur kernel size for alpha edges (odd number, default: 7, 0 disables).",
    )
    parser.add_argument(
        "--debug-mask",
        action="store_true",
        help="Print debug statistics for the first frame mask.",
    )
    parser.add_argument(
        "--rembg-model",
        default=os.getenv("REMBG_MODEL", "u2netp"),
        help="Rembg model name (default: u2netp).",
    )
    parser.add_argument(
        "--rembg-alpha-matting",
        action="store_true",
        help="Enable rembg alpha matting refinement.",
    )
    parser.add_argument(
        "--rembg-fg-threshold",
        type=int,
        default=int(os.getenv("REMBG_FG_THRESHOLD", "240")),
        help="Rembg alpha matting foreground threshold (default: 240).",
    )
    parser.add_argument(
        "--rembg-bg-threshold",
        type=int,
        default=int(os.getenv("REMBG_BG_THRESHOLD", "10")),
        help="Rembg alpha matting background threshold (default: 10).",
    )
    parser.add_argument(
        "--rembg-erode-size",
        type=int,
        default=int(os.getenv("REMBG_ERODE_SIZE", "10")),
        help="Rembg alpha matting erode structure size (default: 10).",
    )
    parser.add_argument(
        "--rembg-base-size",
        type=int,
        default=int(os.getenv("REMBG_BASE_SIZE", "1000")),
        help="Rembg alpha matting base size (default: 1000).",
    )
    parser.add_argument(
        "--shape",
        choices=["rect", "circle"],
        default=os.getenv("OVERLAY_SHAPE", "rect"),
        help="Final overlay shape: rectangle (по умолчанию) или круг (circle).",
    )
    parser.add_argument(
        "--circle-radius",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_RADIUS", "0.35")),
        help="Относительный радиус круга (0-1) при shape=circle (default: 0.35).",
    )
    parser.add_argument(
        "--circle-center-x",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_CENTER_X", "0.5")),
        help="Горизонтальный центр круга (0-1, доля ширины, default: 0.5).",
    )
    parser.add_argument(
        "--circle-center-y",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_CENTER_Y", "0.5")),
        help="Вертикальный центр круга (0-1, доля высоты, default: 0.5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.getenv("SHOTSTACK_API_KEY")
    if not api_key:
        print("Environment variable SHOTSTACK_API_KEY is required.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve()

    container = args.container
    if output_path.suffix.lower() in {".mov", ".qt"}:
        container = "mov"
    elif output_path.suffix.lower() == ".webm":
        container = "webm"

    try:
        public_url = prepare_overlay(
            args.input_url,
            output_path,
            args.stage,
            api_key,
            container,
            threshold=max(0.0, min(1.0, args.threshold)),
            feather=args.feather,
            debug=args.debug_mask,
            engine=args.engine,
            rembg_model=args.rembg_model,
            rembg_alpha_matting=args.rembg_alpha_matting,
            rembg_fg_threshold=args.rembg_fg_threshold,
            rembg_bg_threshold=args.rembg_bg_threshold,
            rembg_erode_size=args.rembg_erode_size,
            rembg_base_size=args.rembg_base_size,
            shape=args.shape,
            circle_radius=args.circle_radius,
            circle_center_x=args.circle_center_x,
            circle_center_y=args.circle_center_y,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\nUse this URL in your Shotstack JSON spec:")
    print(public_url)


if __name__ == "__main__":
    main()
